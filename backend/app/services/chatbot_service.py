"""Chatbot service — wraps ADK agent runner for single-turn Q&A."""

import logging
from uuid import UUID

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.cooperative_agent import create_cooperative_agent

logger = logging.getLogger("akoweai")

_FALLBACK_RESPONSE = (
    "I wasn't able to process that question. Please try rephrasing."
)


async def answer_chatbot_question(question: str, coop_id: UUID) -> str:
    """
    Run the cooperative advisor agent with the given question and return
    its natural language response.

    Always returns a string — ADK errors are caught and replaced with the
    fallback response so the endpoint always returns HTTP 200.
    """
    try:
        agent = create_cooperative_agent(coop_id)
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="akoweai",
            session_service=session_service,
        )

        coop_id_str = str(coop_id)
        await session_service.create_session(
            app_name="akoweai",
            user_id=coop_id_str,
            session_id=coop_id_str,
        )

        new_message = types.Content(
            role="user",
            parts=[types.Part(text=question)],
        )

        async for event in runner.run_async(
            user_id=coop_id_str,
            session_id=coop_id_str,
            new_message=new_message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                return "".join(
                    part.text
                    for part in event.content.parts
                    if hasattr(part, "text") and part.text
                )

    except Exception as exc:
        logger.error(
            "Chatbot agent failed for coop=%s question=%r: %s",
            coop_id,
            question[:100],
            exc,
        )

    return _FALLBACK_RESPONSE