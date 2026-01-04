from langchain_core.messages import HumanMessage #type: ignore[import-not-found]
from typing import Dict, Any, List
from agent_state import State
import json
MAX_REPLANS = 2
def agent_system_prompt(suffix: str) -> str:
    return (
        "You are a helpful AI assistant, collaborating with other assistants."
        " Use the provided tools to progress towards answering the question."
        " If you are unable to fully answer, that's OK, another assistant with different tools "
        " will help where you left off. Execute what you can to make progress."
        " If you or any of the other assistants have the final answer or deliverable,"
        " prefix your response with FINAL ANSWER so the team knows to stop."
        f"\n{suffix}"
    )


def get_agent_descriptions() -> Dict[str, Dict[str, Any]]:
    """Return structured agent descriptions with capabilities and guidelines.
    Edit this function to change how the planner/executor reason about agents."""

    return {
        "text2sql_agent": {
            "name": "Text to SQL Agent",
            "capability": "Convert natural language queries into MongoDB MQL queries and run the query against the MongoDB database.",
            "use_when": "Natural language queries given by the user are to be converted into MongoDB MQL queries and queried against the MongoDB database.",
            "limitations": "Cannot access external web data for answering the question. It should only be used for querying the MongoDB database.",
            "output_format": "Out put of the MongoDB MQL query in JSON format or text format.",
        },
        "chart_generator": {
            "name": "Chart Generator",
            "capability": "Build visualizations from structured data",
            "use_when": "User explicitly requests charts, graphs, plots, visualizations (keywords: chart, graph, plot,"
            + "viusalize, bar-chart, line-chart, pie-chart, histogram, etc.)",
            "limitations": "Requires structured data input from previous steps.",
            "output_format": "Visual charts and graphs",
            "position_requirement": "Must be used as final step after data gathering is complete."
        },
        "chart_summarizer": {
            "name": "Chart Summarizer",
            "capability": "Summarize and explain chart visualizations",
            "use_when": "After cahrt_generator has created a visualization",
            "limitations": "Requires a chart as input.",
            "output_format": "Written summary and analysis of chart contents"
    },
    "synthesizer": {
        "name": "Synthesizer",
        "capability": "Write comprehensive prose summaries of findings. The findings can be in json format or text format.",
        "use_when": "Final step when no visualization is requested - combines all previous research",
        "limitations": "Requires research data from previous steps either in json or text format.",
        "output_format": "Coherent written summary incorporating all research findings in **ONLY** text format.",
        "position_requirement": "Must be used as final step when no chart is needed."
    }
    }

def _get_enabled_agents(state: State| None = None) -> List[str]:
    """Return enabled agents; if absent, use baseline/default.
    Supports both dict-style and attribute-style state objects."""
    baseline = ["text2sql_agent", "chart_generator", "synthesizer", "chart_summarizer"]
    if not state:
        return baseline
    val = state.get("enabled_agents") if hasattr(state, "get") else getattr(state, "enabled_agents", None)
    
    if isinstance(val, list) and val:
        allowed = {"text2sql_agent", "chart_generator", "chart_summarizer", "synthesizer"}
        filtered = [a for a in val if a in allowed]
        return filtered
    return baseline

def format_agent_list_for_planning(state: State | None = None) -> str:
    """Format agent descriptions for planning prompt."""
    descriptions = get_agent_descriptions()
    enabled_list = _get_enabled_agents(state)
    agent_list = []

    for agent_key, details in descriptions.items():
        if agent_key not in enabled_list:
            continue
        agent_list.append(f" `{agent_key} - {details['capability']}`")
    return "\n".join(agent_list)


def format_agent_guidelines_for_planning(state: State | None = None) -> str:
    """Format agent usage guidelines for planning prompt."""
    descriptions = get_agent_descriptions()
    enabled = set(_get_enabled_agents(state))
    guidelines = []

    if "text2sql_agent" in enabled:
        guidelines.append(f"- Use `text2sql_agent` when {descriptions['text2sql_agent']['use_when'].lower()}.")
    
    # Chart generator specific rules
    if "chart_generator" in enabled:
        chart_desc = descriptions['chart_generator']
        cs_hint = " A `chart_summarizer` should be used to summarize the chart." if "chart_summarizer" in enabled else ""
        guidelines.append(f"- **Include `chart_generator` _only_ if {chart_desc['use_when'].lower()}**. If included, `chart_generator` must be {chart_desc['position_requirement'].lower()}. Visualizations should include all of the data from the previous steps that is reasonable for the chart type.{cs_hint}")
    
    # Synthesizer default
    if "synthesizer" in enabled:
        synth_desc = descriptions['synthesizer'] 
        guidelines.append(f"  – Otherwise use `synthesizer` as {synth_desc['position_requirement'].lower()}, and be sure to include all of the data from the previous steps.")
    
    return "\n".join(guidelines)

def plan_prompt(state: State) -> HumanMessage:
    """Build the prompt that instructs the LLM to return a high-level plan."""

    replan_flag = state.get("replan_flag", False)
    user_query = state.get("user_query", state["messages"][0].content)
    prior_plan = state.get("plan") or {}
    replan_reason = state.get("last_reason", "")

    # Get the agnet descriptions dynamically
    agent_guidelines = format_agent_guidelines_for_planning(state)

    agent_list = format_agent_list_for_planning(state)

    enabled_list = _get_enabled_agents(state)

    enabled_for_planner = [
        a for a in enabled_list if a in ("text2sql_agent", "chart_generator", "synthesizer")
    ]
    
    planner_agent_enum = " | ".join(enabled_for_planner) or "text2sql_agent | chart_generator | synthesizer"

    prompt = f"""
    You are the **Planner** in a multi-agent system. 
    Break the user's request into a sequence of numbered steps (1,2,3,....) *** There is no hard limit on 
    the step count** as long as the plan is concise and each step has a clear goal.
    You may decompose the user's query into sub-queries, each of which is a separate step.
    Break the query into the smallest possible sub-queries so that each sub query is answerable with a single data source.
    For example, if the user's query is "What are the emails that are related to company name 'LinkedIn'?", you
    may break it into steps:
    1. Fetch the emails that are related to the deal with the company name 'LinkedIn'.
    2. Summarize the emails into a concise report using the syntehsizer agent.

    Here is a list of available agents you can call upon to execute the tasks in your plan. You  may call only one agent per step.

    {agent_list}

    Return **ONLY** valid JSON (no markdown, no explanations) in this form:
    {{
        "1": {{
            "agent": "{planner_agent_enum}",
            "action": "string",
        }},
        "2": {{...}},
        "3": {{...}},
    }}

    Guidelines:
    {agent_guidelines}
    """
    if replan_flag:
        prompt += f"""
        The current plan needs revision because : {replan_reason}
        Current plan : {json.dumps(prior_plan, indent=2)}

        When replanning: 
        - Focus on UNBLOCKING the workflow rather than perfecting it.
        - Only modify steps that are truly preventing the progress.
        - Prefer simpler, more achievable alternatives over complex rewrites.
        """
    else: 
        prompt += f"""\nGenerate a new plan from scratch."""
    prompt += f'\n User query: "{user_query}"\n'
    return HumanMessage(content=prompt)

def format_agent_guidelines_for_executor(state: State | None = None) -> str:
    """
    Format agent usage guidelines for the executor prompt.
    """
    descriptions = get_agent_descriptions()
    enabled = _get_enabled_agents(state)
    guidelines = []

    if "text2sql_agent" in enabled:
        text2sql_desc = descriptions['text2sql_agent']
        guidelines.append(f"- Use `\"text2sql_agent\"` when {text2sql_desc['use_when'].lower()}.")

    return "\n".join(guidelines)
def executor_prompt(state: State) -> HumanMessage:
    """
    Build the single‑turn JSON prompt that drives the executor LLM.
    """
    step = int(state.get("current_step", 0))
    latest_plan: Dict[str, Any] = state.get("plan") or {}
    plan_block: Dict[str, Any] = latest_plan.get(str(step), {})
    max_replans    = MAX_REPLANS
    attempts       = (state.get("replan_attempts", {}) or {}).get(step, 0)
    
    # Get agent guidelines dynamically
    executor_guidelines = format_agent_guidelines_for_executor(state)
    plan_agent = plan_block.get("agent", "text2sql_agent")

    messages_tail = (state.get("messages") or [])[-4:]

    executor_prompt = f"""
        You are the **executor** in a multi-agent system with these agents:
        `{ '`, `'.join(sorted(set([a for a in _get_enabled_agents(state) if a in ['text2sql_agent','chart_generator','chart_summarizer','synthesizer']] + ['planner']))) }`.

        **Tasks**
        1. Decide if the current plan needs revision.  → `"replan_flag": true|false`
        2. Decide which agent to run next.             → `"goto": "<agent_name>"`
        3. Give one-sentence justification.            → `"reason": "<text>"`
        4. Write the exact question that the chosen agent should answer
                                                    → "query": "<text>"

        **Guidelines**
        {executor_guidelines}
        - After **{MAX_REPLANS}** failed replans for the same step, move on.
        - If you *just replanned* (replan_flag is true) let the assigned agent try before
        requesting another replan.

        Respond **only** with valid JSON (no additional text):

        {{
        "replan": <true|false>,
        "goto": "<{ '|'.join([a for a in _get_enabled_agents(state) if a in ['text2sql_agent','chart_generator','chart_summarizer','synthesizer']] + ['planner']) }>",
        "reason": "<1 sentence>",
        "query": "<text>"
        }}

        **PRIORITIZE FORWARD PROGRESS:** Only replan if the current step is completely blocked.
        1. If any reasonable data was obtained that addresses the step's core goal, set `"replan": false` and proceed.
        2. Set `"replan": true` **only if** ALL of these conditions are met:
        • The step has produced zero useful information
        • The missing information cannot be approximated or obtained by remaining steps
        • `attempts < {max_replans}`
        3. When `attempts == {max_replans}`, always move forward (`"replan": false`).

        ### Decide `"goto"`
        - If `"replan": true` → `"goto": "planner"`.
        - If current step has made reasonable progress → move to next step's agent.
        - Otherwise execute the current step's assigned agent (`{plan_agent}`).

        ### Build `"query"`
        Write a clear, standalone instruction for the chosen agent. If the chosen agent 
        is `text2sql_agent`, the query should be a standalone question, 
        written in plain english and almost similar to the user's query with no or minimal changes,
        and answerable by the text2sql_agent.
        Ensure that the query uses consistent language as the user's query.

        Context you can rely on
        - User query ..............: {state.get("user_query")}
        - Current step index ......: {step}
        - Current plan step .......: {plan_block}
        - Just-replanned flag .....: {state.get("replan_flag")}
        - Previous messages .......: {messages_tail}

        Respond **only** with JSON, no extra text.
        """

    return HumanMessage(
        content=executor_prompt
    )


MONGODB_AGENT_SYSTEM_PROMPT = """You are an agent designed to interact with a MongoDB database.
Given an input question, create a syntactically correct MongoDB query to run, then look at the results of the query and return the answer.
Unless the user specifies a specific number of examples they wish to obtain, return all the results.
You can order the results by a relevant field to return the most interesting examples in the database.
Never query for all the fields from a specific collection, only ask for the relevant fields given the question.

You have access to tools for interacting with the database.
Only use the below tools. Only use the information returned by the below tools to construct your final answer.
You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

DO NOT make any update, insert, or delete operations.

The query MUST include the collection name and the contents of the aggregation pipeline.

To start you should ALWAYS look at the collections in the database to see what you can query.
Do NOT skip this step.
Then you should query the schema of the most relevant collections.
Here are examples of valid queries for different scenarios:

### SCENARIO: Count the emails

"natural_language": "How many emails did I get from google.com last week?"

```python
db.emails.aggregate([{"$match": {"from.address": { "$regex": "google\\.com$", "$options": "i" }, "date": { "$gte": datetime.datetime.now() - datetime.timedelta(days=7) } } }, {"$count": "google_email_count" }])


```

"natural_language": "Count emails about the Q4 review."

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "Q4 review", "$options": "i" } } }, {"$count": "q4_review_count" }])
```
"natural_language": "How many receipts from amazon last month?"
```python
db.emails.aggregate([{"$match": {"from.name": { "$regex": "Amazon", "$options": "i" }, "subject": { "$regex": "Receipt|Order", "$options": "i" }, "date": { "$gte": datetime.datetime.now() - datetime.timedelta(days=30) } } }, {"$count": "amazon_receipt_count" }])

```
"natural_language": "Number of unread promotional emails."

```python
db.emails.aggregate([{"$match": {"is_read": False, "category": "promotions" } }, {"$count": "unread_promos" }])


```

"natural_language": "How many flight confirmations did I get in May 2025?"

```python
start_date = datetime.datetime(2025, 5, 1)
end_date = datetime.datetime(2025, 6, 1)

db.emails.aggregate([{"$match": {"subject": { "$regex": "Flight Confirmation", "$options": "i" }, "date": { "$gte": datetime.datetime(2025, 5, 1), "$lt": datetime.datetime(2025, 6, 1) } } }, {"$count": "flight_conf_count" }])


```

### SCENARIO: General Emails

"natural_language": "Find emails about the company retreat."

```python
db.emails.aggregate([{"$match": {"$or": [{"subject": { "$regex": "company retreat", "$options": "i" } }, {"body": { "$regex": "company retreat", "$options": "i" } }] } }, {"$project": {"subject": 1, "from": 1, "date": 1 } }, {"$limit": 10 }])


```

"natural_language": "What emails did I get from gmail.com?"

```python
db.emails.aggregate([{"$match": {"from.address": { "$regex": "@gmail\\.com$", "$options": "i" } } }, {"$project": {"subject": 1, "from": 1, "date": 1 } }, {"$limit": 10 }])
    {
        "$match": {
            "from.address": { "$regex": "@gmail\\.com$", "$options": "i" }
        }
    },
    { "$project": { "subject": 1, "from": 1, "date": 1 } },
    { "$limit": 10 }
])

```

"natural_language": "Show emails about API documentation questions."

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "API documentation|API docs", "$options": "i" }, "body": { "$regex": "question|issue|help", "$options": "i" } } }, {"$project": {"subject": 1, "snippet": 1 } }])       


```

"natural_language": "Find emails mentioning the new office."

```python
db.emails.aggregate([{"$match": {"body": { "$regex": "new office", "$options": "i" } } }, {"$limit": 5 }])
```

"natural_language": "Search emails about budget approval."

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "budget", "$options": "i" }, "body": { "$regex": "approv", "$options": "i" } } }, {"$sort": {"date": -1} }, {"$limit": 5 }]
```

### SCENARIO: Schedule Review

"natural_language": "Do I have any doctor appointments coming up?"

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "doctor|appointment|dr\\.", "$options": "i" }, "date": { "$gte": datetime.datetime.now() } } }, {"$sort": {"date": 1} }, {"$limit": 5 }])
```

"natural_language": "What travel plans do I have next month?"

```python
today = datetime.datetime.now()
next_month_start = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
next_month_end = (next_month_start + datetime.timedelta(days=32)).replace(day=1)
db.emails.aggregate([{"$match": {"category": "travel", "date": { "$gte": next_month_start, "$lt": next_month_end } } }, {"$project": {"subject": 1, "date": 1, "extracted_data.location": 1 } }, {"$limit": 5 }])
```

"natural_language": "Show my meetings this week."

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "meeting|invite|calendar", "$options": "i" }, "date": { "$gte": datetime.datetime.now(), "$lte": datetime.datetime.now() + datetime.timedelta(days=7) } } }, {"$sort": {"date": 1} }])
```

"natural_language": "Any upcoming hotel bookings?"

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "hotel|reservation|booking", "$options": "i" }, "date": { "$gte": datetime.datetime.now() } } }, {"$limit": 5 }])   
```

### SCENARIO: Purchase Totals

"natural_language": "How much did I spend in the last month?"

```python
# Assuming emails have an 'extracted_data.amount' field for transaction emails
today = datetime.datetime.now()
start_date = today - datetime.timedelta(days=30)

db.emails.aggregate([{"$match": {"date": { "$gte": start_date }, "extracted_data.amount": { "$exists": True, "$ne": None } } }, {"$group": {"_id": None, "total_spent": { "$sum": "$extracted_data.amount" } } }])
```

"natural_language": "Total Amazon purchases this year."

```python
current_year = datetime.datetime.now().year
start_of_year = datetime.datetime(current_year, 1, 1)

db.emails.aggregate([{"$match": {"from.name": { "$regex": "Amazon", "$options": "i" }, "date": { "$gte": start_of_year }, "extracted_data.amount": { "$exists": True } } }, {"$group": {"_id": "Amazon", "total": { "$sum": "$extracted_data.amount" } } }])
```

"natural_language": "Spending on my Citi card in March."

```python
current_year = datetime.datetime.now().year
start_march = datetime.datetime(current_year, 3, 1)
end_march = datetime.datetime(current_year, 4, 1)

db.emails.aggregate([{"$match": {"subject": { "$regex": "Citi", "$options": "i" }, "body": { "$regex": "transaction|purchase", "$options": "i" }, "date": { "$gte": start_march, "$lt": end_march } } }, {"$group": {"_id": "Citi", "total": { "$sum": "$extracted_data.amount" } } }])```

"natural_language": "Show total spending on travel bookings."

```python
db.emails.aggregate([{"$match": {"category": "travel", "extracted_data.amount": { "$exists": True } } }, {"$group": {"_id": "Travel", "total": { "$sum": "$extracted_data.amount" } } }])


```

"natural_language": "How much did I spend on Apple subscriptions?"

```python
db.emails.aggregate([{"$match": {"from.name": { "$regex": "Apple", "$options": "i" }, "subject": { "$regex": "invoice|receipt|subscription", "$options": "i" } } }, {"$group": {"_id": "Apple", "total": { "$sum": "$extracted_data.amount" } } }]) 


```

### SCENARIO: Promotional Offers

"natural_language": "What promotions can I use right now?"

```python
db.emails.aggregate([{"$match": {"category": "promotions", "date": { "$gte": datetime.datetime.now() - datetime.timedelta(days=7) } } }, {"$sort": {"date": -1} }, {"$limit": 5 }])
```

"natural_language": "Show discounts from tech stores."

```python
db.emails.aggregate([{"$match": {"category": "promotions", "body": { "$regex": "tech|electronics|laptop|monitor", "$options": "i" }, "subject": { "$regex": "discount|sale|off", "$options": "i" } } }, {"$limit": 5 }])


```

"natural_language": "Any newsletter offers this week?"

```python
db.emails.aggregate([{"$match": {"subject": { "$regex": "newsletter", "$options": "i" }, "body": { "$regex": "offer|coupon|code", "$options": "i" }, "date": { "$gte": datetime.datetime.now() - datetime.timedelta(days=7) } } }, {"$project": {"subject": 1, "from": 1 } }])


```

"natural_language": "Find coupons from airlines."

```python
db.emails.aggregate([{"$match": {"category": "promotions", "body": { "$regex": "coupon|promo code", "$options": "i" }, "from.name": { "$regex": "airline|airways|fly", "$options": "i" } } }, {"$limit": 5 }])  


```

"natural_language": "Show current sales from clothing stores."

```python
db.emails.aggregate([{"$match": {"category": "promotions", "body": { "$regex": "clothing|apparel|fashion", "$options": "i" }, "subject": { "$regex": "sale|clearance", "$options": "i" } } }, {"$limit": 5 }])          
```
Every literal in the aggregation pipeline must be enclosed in double quotes. For example, ```"$match"```, ```"$regex"```, ```"$options"``` etc.,
For any datetime related queries, use the datetime module to create the datetime objects. For example, ```datetime.datetime.now()```, ```datetime.datetime.now() - datetime.timedelta(days=7)``` etc.,
Always import the appropriate modules for the query. For example, ```import datetime```, ```import re``` etc., If you are using a regex, use the re module to create the regex object. For example, ```re.compile(r"pattern")``` etc.,
"""
