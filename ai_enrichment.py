import logging
import os
from openai import OpenAI

logger = logging.getLogger(__name__)


def get_ai_notes(intake_data: dict) -> str:
    """Call gpt-4o-mini to enrich intake data. Retries up to 3x; returns '' on failure."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ""

    client = OpenAI(api_key=api_key)

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
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a senior consultant."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=700,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("AI enrichment attempt %d failed: %s", attempt + 1, exc)
            if attempt == 2:
                return ""

    return ""
