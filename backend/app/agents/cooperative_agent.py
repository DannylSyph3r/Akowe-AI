"""
ADK cooperative advisor agent — Phase 11.

One agent is instantiated per API request, scoped to a single cooperative
via coop_id baked into the system prompt at creation time.
The query_cooperative_data tool runs synchronously on the readonly_engine.
"""

import json
import logging
from uuid import UUID

from google.adk.agents import Agent
from google.adk.tools import tool
from sqlalchemy import text

from app.prompts.chatbot_agent import format_chatbot_prompt

logger = logging.getLogger("akoweai")


@tool
def query_cooperative_data(sql: str) -> str:
    """
    Execute a read-only SQL SELECT against the cooperative database.
    Automatically enforces LIMIT 200 if not already present.
    Returns results as a JSON string, or a descriptive error string on failure.
    """
    from app.core.database import readonly_engine

    if readonly_engine is None:
        return "ERROR: Read-only database is not configured. Ask your administrator to set READONLY_DATABASE_URL."

    # Enforce LIMIT 200
    normalized = sql.strip().rstrip(";")
    if "limit" not in normalized.lower():
        normalized = f"{normalized} LIMIT 200"

    try:
        with readonly_engine.connect() as conn:
            result = conn.execute(text(normalized))
            rows = [dict(row._mapping) for row in result.fetchall()]
            return json.dumps(rows, default=str)
    except Exception as exc:
        logger.warning("query_cooperative_data failed: %s", exc)
        return f"ERROR: Query failed — {exc}"


def create_cooperative_agent(coop_id: UUID) -> Agent:
    """
    Instantiate an ADK Agent scoped to the given cooperative.
    The coop_id is baked into the system prompt — it cannot be overridden
    by user input at runtime.
    """
    return Agent(
        name="cooperative_advisor",
        model="gemini-3.1-pro-preview",
        instruction=format_chatbot_prompt(str(coop_id)),
        tools=[query_cooperative_data],
    )