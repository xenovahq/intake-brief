import logging
import os
from anthropic import Anthropic

logger = logging.getLogger(__name__)


def get_ai_notes(intake_data: dict) -> str:
    """Call Claude Haiku to enrich intake data. Retries up to 3x; returns '' on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    client = Anthropic(api_key=api_key)

    data_lines = "\n".join(
        f"{k.replace('_', ' ').title()}: {v}"
        for k, v in intake_data.items()
        if v and v.strip()
    )

    user_prompt = (
        f"Given this client intake data:\n\n{data_lines}\n\n"
        "Write:\n"
        "(1) a 3-sentence project summary in the client's voice,\n"
        "(2) 2-3 likely risk factors,\n"
        "(3) a recommended engagement structure (phases + rough timeline).\n\n"
        "Be specific and business-focused."
    )

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system="You are a senior consultant.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            notes = message.content[0].text
            return notes.strip()
        except Exception as exc:
            logger.warning("AI enrichment attempt %d failed: %s", attempt + 1, exc)
            if attempt == 2:
                return ""

    return ""
