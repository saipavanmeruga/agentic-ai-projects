import argparse
import base64
import email.utils
import hashlib
import hmac
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

# Google Gmail API
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("email_ingest")

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://<USER>:<PASS>@<CLUSTER>/<DB>?retryWrites=true&w=majority",
)
MONGODB_DB = os.getenv("MONGODB_DB", "your_db")
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "emails")

# Webhook auth (HMAC)
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "REPLACE_ME_WITH_STRONG_SECRET")
SIG_MAX_SKEW_SECONDS = int(os.getenv("SIG_MAX_SKEW_SECONDS", "300"))

PORT = int(os.getenv("PORT", "8080"))

# Gmail OAuth
GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "client_secret.json")  # placeholder
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "gmail_token.json")  # placeholder secure path
GMAIL_SCOPES = [
    # Readonly is sufficient for ingestion
    "https://www.googleapis.com/auth/gmail.readonly",
]
# How many days back to ingest
DEFAULT_LAST_DAYS = int(os.getenv("GMAIL_LAST_DAYS", "10"))


mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = mongo_client[MONGODB_DB]
emails_col = db[MONGODB_COLLECTION]

def ensure_indexes() -> None:
    """
    Idempotency key is Gmail message id (provider_message_id).
    """
    emails_col.create_index([("provider", ASCENDING), ("provider_message_id", ASCENDING)], unique=True)
    emails_col.create_index([("user_id", ASCENDING), ("received_at", ASCENDING)])
    emails_col.create_index([("thread_id", ASCENDING)])


try:
    ensure_indexes()
except Exception as e:
    logger.warning("Index creation failed or skipped: %s", e)



def save_credentials(creds: Credentials, token_file: str) -> None:
    os.makedirs(os.path.dirname(token_file) or ".", exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def interactive_gmail_auth(client_secrets_file: str, token_file: str, scopes: List[str]) -> Credentials:
    """
    Run once manually to authorize and save refreshable token to disk.
    """
    if not os.path.exists(client_secrets_file):
        raise FileNotFoundError(
            f"Missing Google OAuth client secrets file at '{client_secrets_file}'. "
            "Download from Google Cloud Console (OAuth client ID)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, scopes=scopes)
    creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="")
    save_credentials(creds, token_file)
    logger.info("Gmail OAuth complete. Token saved to %s", token_file)
    return creds


def get_gmail_service() -> Any:
    """
    Loads token and refreshes it if needed.
    If token is absent, instruct user to run --gmail-auth.
    """
    creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GMAIL_SCOPES)
    if not creds:
        raise RuntimeError(
            f"No Gmail token found at '{GOOGLE_TOKEN_FILE}'. Run: python email_ingest_service.py --gmail-auth"
        )

    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())
        save_credentials(creds, GOOGLE_TOKEN_FILE)
        logger.info("Refreshed Gmail token.")
    elif not creds.valid:
        raise RuntimeError("Gmail credentials invalid. Re-run: --gmail-auth")

    # cache_discovery=False to avoid file writes in some environments
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ----------------------------
# Gmail Fetch + Parse
# ----------------------------


def gmail_query_last_days(days: int) -> str:
    """
    Gmail search query. 'newer_than:10d' is generally reliable for "last N days".
    """
    return f"newer_than:{days}d"


def list_message_ids(service: Any, user_id: str, q: str) -> List[str]:
    ids: List[str] = []
    page_token: Optional[str] = None

    while True:
        resp = (
            service.users()
            .messages()
            .list(userId=user_id, q=q, pageToken=page_token, maxResults=500)
            .execute()
        )
        msgs = resp.get("messages", [])
        ids.extend([m["id"] for m in msgs if "id" in m])

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return ids


def _decode_base64url(data: str) -> str:
    """
    Gmail returns body parts as base64url.
    """
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_headers(headers: List[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for h in headers or []:
        name = (h.get("name") or "").strip()
        value = (h.get("value") or "").strip()
        if name:
            out[name.lower()] = value
    return out


def _walk_parts_for_bodies(payload: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (body_text, body_html). Prefer direct body if present; otherwise walk parts recursively.
    """
    body_text = ""
    body_html = ""

    def walk(part: Dict[str, Any]) -> None:
        nonlocal body_text, body_html
        mime = (part.get("mimeType") or "").lower()
        body = part.get("body") or {}
        data = body.get("data")

        if data and mime == "text/plain" and not body_text:
            body_text = _decode_base64url(data)
        elif data and mime == "text/html" and not body_html:
            body_html = _decode_base64url(data)

        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload or {})
    return body_text, body_html


def _extract_addresses(value: str) -> List[Dict[str, str]]:
    """
    Parses RFC5322 address lists into [{"name":..., "email":...}, ...]
    """
    if not value:
        return []
    parsed = email.utils.getaddresses([value])
    out = []
    for name, addr in parsed:
        if addr:
            out.append({"name": name or "", "email": addr})
    return out


def parse_gmail_message(full_msg: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    """
    Converts Gmail API message (format=full) into Mongo-ready document.
    """
    msg_id = full_msg.get("id")
    thread_id = full_msg.get("threadId")
    internal_date_ms = full_msg.get("internalDate")

    payload = full_msg.get("payload", {}) or {}
    headers = _extract_headers(payload.get("headers", []))

    subject = headers.get("subject")
    from_raw = headers.get("from", "")
    to_raw = headers.get("to", "")
    cc_raw = headers.get("cc", "")
    bcc_raw = headers.get("bcc", "")

    snippet = full_msg.get("snippet")
    body_text, body_html = _walk_parts_for_bodies(payload)

    # Received time
    if internal_date_ms:
        try:
            received_at = int(int(internal_date_ms) / 1000)
        except Exception:
            received_at = int(time.time())
    else:
        received_at = int(time.time())

    # Basic attachment metadata
    attachments: List[Dict[str, Any]] = []
    # Walk parts to find filenames / attachmentIds
    def walk_for_attachments(part: Dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        att_id = body.get("attachmentId")
        if filename and att_id:
            attachments.append(
                {
                    "filename": filename,
                    "content_type": part.get("mimeType"),
                    "size": body.get("size"),
                    "attachment_id": att_id,
                }
            )
        for child in part.get("parts", []) or []:
            walk_for_attachments(child)

    walk_for_attachments(payload)

    doc: Dict[str, Any] = {
        "user_id": user_email,  # partition by actual inbox identity
        "provider": "gmail",
        "provider_message_id": msg_id,
        "thread_id": thread_id,
        "subject": subject,
        "from": (_extract_addresses(from_raw)[0] if _extract_addresses(from_raw) else {"name": "", "email": ""}),
        "to": _extract_addresses(to_raw),
        "cc": _extract_addresses(cc_raw),
        "bcc": _extract_addresses(bcc_raw),
        "snippet": snippet,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "received_at": received_at,
        "in_gmail_label_ids": full_msg.get("labelIds", []),
        "ingested_at": int(time.time()),
        # Keep raw for debugging/auditing (optional; can be large)
        "raw": {
            "historyId": full_msg.get("historyId"),
            "sizeEstimate": full_msg.get("sizeEstimate"),
        },
    }
    return doc


# ----------------------------
# Ingest into MongoDB
# ----------------------------


def upsert_email_doc(doc: Dict[str, Any]) -> str:
    """
    Insert-only with unique index on (provider, provider_message_id).
    Duplicates are treated as success (idempotent).
    """
    try:
        res = emails_col.insert_one(doc)
        return f"inserted:{res.inserted_id}"
    except DuplicateKeyError:
        return "duplicate"
    except Exception as e:
        logger.exception("Mongo insert failed")
        raise RuntimeError(f"Mongo insert failed: {e}") from e


def ingest_last_n_days(days: int = DEFAULT_LAST_DAYS) -> Dict[str, Any]:
    service = get_gmail_service()

    profile = service.users().getProfile(userId="me").execute()
    user_email = profile.get("emailAddress", "me")

    q = gmail_query_last_days(days)
    msg_ids = list_message_ids(service, user_id="me", q=q)

    inserted = 0
    duplicates = 0
    failed = 0

    for mid in msg_ids:
        try:
            full_msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
            doc = parse_gmail_message(full_msg, user_email=user_email)
            status = upsert_email_doc(doc)
            if status.startswith("inserted"):
                inserted += 1
            else:
                duplicates += 1
        except Exception as e:
            failed += 1
            logger.warning("Failed message id=%s error=%s", mid, e)

    summary = {
        "user": user_email,
        "query": q,
        "total_found": len(msg_ids),
        "inserted": inserted,
        "duplicates": duplicates,
        "failed": failed,
        "days": days,
    }
    logger.info("Ingest summary: %s", summary)
    return summary


# ----------------------------
# Webhook endpoint (optional pipeline trigger)
# ----------------------------

app = Flask(__name__)


@app.get("/health")
def health() -> Any:
    try:
        mongo_client.admin.command("ping")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "degraded", "error": str(e)}), 503


@app.post("/webhook/email")
def webhook_email() -> Any:
    """
    Receives normalized email payloads and inserts into MongoDB.
    HMAC-authenticated via X-Timestamp + X-Signature.
    """
    raw_body = request.get_data() or b""
    ok, reason = verify_request(WEBHOOK_SHARED_SECRET, dict(request.headers), raw_body)
    if not ok:
        return jsonify({"error": "unauthorized", "reason": reason}), 401

    try:
        payload = request.get_json(force=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "bad_request", "reason": "JSON body must be an object"}), 400
    except Exception as e:
        return jsonify({"error": "bad_request", "reason": f"Invalid JSON: {e}"}), 400

    # Minimal validation
    if not payload.get("user_id") or not payload.get("provider_message_id"):
        return jsonify({"error": "bad_request", "reason": "Missing user_id or provider_message_id"}), 400

    doc = {
        **payload,
        "provider": payload.get("provider", "webhook"),
        "ingested_at": int(time.time()),
        "received_at": int(payload.get("received_at") or time.time()),
    }

    try:
        status = upsert_email_doc(doc)
        code = 201 if status.startswith("inserted") else 200
        return jsonify({"status": status}), code
    except Exception as e:
        return jsonify({"error": "server_error", "reason": str(e)}), 500


@app.post("/ingest/last10days")
def ingest_last10days_endpoint() -> Any:
    """
    Optional HTTP trigger to run the Gmail pull+ingest.
    You can protect this with an internal auth layer (API key, mTLS, etc.).
    For minimalism, we reuse the webhook HMAC scheme here too.
    """
    raw_body = request.get_data() or b""
    ok, reason = verify_request(WEBHOOK_SHARED_SECRET, dict(request.headers), raw_body)
    if not ok:
        return jsonify({"error": "unauthorized", "reason": reason}), 401

    days = DEFAULT_LAST_DAYS
    try:
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict) and body.get("days"):
            days = int(body["days"])
    except Exception:
        pass

    try:
        summary = ingest_last_n_days(days=days)
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({"error": "server_error", "reason": str(e)}), 500


# ----------------------------
# CLI Entrypoint
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Gmail -> MongoDB ingest + webhook service")
    parser.add_argument("--gmail-auth", action="store_true", help="Run interactive Gmail OAuth and store token")
    parser.add_argument("--ingest-last-10-days", action="store_true", help="Fetch and ingest last 10 days of emails")
    parser.add_argument("--serve", action="store_true", help="Run webhook HTTP server")
    parser.add_argument("--days", type=int, default=DEFAULT_LAST_DAYS, help="Days back to ingest (default 10)")
    args = parser.parse_args()

    if args.gmail_auth:
        interactive_gmail_auth(GOOGLE_CLIENT_SECRETS_FILE, GOOGLE_TOKEN_FILE, GMAIL_SCOPES)
        return

    if args.ingest_last_10_days:
        summary = ingest_last_n_days(days=args.days)
        # Print for cron logs
        print(json.dumps(summary, ensure_ascii=False))
        return

    if args.serve:
        logger.info("Starting server on port %s", PORT)
        app.run(host="0.0.0.0", port=PORT)
        return

    parser.print_help()


if __name__ == "__main__":
    main()