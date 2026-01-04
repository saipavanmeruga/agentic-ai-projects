from email_assistant.email_client.email_client import EmailClient
client = EmailClient()
q = client.build_query(topic="tldrnewsletter.com", start_date="2025/12/24", end_date="2025/12/25")
emails = client.search(q, max_results=1, include_body_preview=True)
for e in emails:
    print(f"Sender: {e.sender}, Subject: {e.subject}, Date: {e.date}, Snippet: {e.snippet}")