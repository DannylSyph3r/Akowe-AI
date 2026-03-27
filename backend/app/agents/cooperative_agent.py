"""Cooperative advisor agent powered by ADK."""

import json
import logging
from uuid import UUID

from google.adk.agents import LlmAgent
from sqlalchemy import text

from app.prompts.chatbot_agent import format_chatbot_prompt

logger = logging.getLogger("akoweai")


def query_cooperative_data(sql: str) -> str:
    """Execute read-only SQL SELECT, auto-limiting to 200 rows."""
    from app.core.database import readonly_engine

    if readonly_engine is None:
        return "ERROR: Read-only database is not configured. Ask your administrator to set READONLY_DATABASE_URL."

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


def create_cooperative_agent(coop_id: UUID) -> LlmAgent:
    """Create an agent scoped to a specific cooperative."""
    return LlmAgent(
        name="cooperative_advisor",
        model="gemini-3-flash-preview",
        instruction=format_chatbot_prompt(str(coop_id)),
        tools=[query_cooperative_data],
    )