import json
from pathlib import Path
from dealtracker.ai.schemas import DocumentExtraction, SYSTEM_PROMPT
from dealtracker.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


def extract(text: str) -> tuple[DocumentExtraction, str]:
    """
    Use Claude to extract structured data from document text.
    Returns (DocumentExtraction, model_used).
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Please extract information from this document:\n\n{text}",
            }
        ],
    )

    raw_response = message.content[0].text.strip()
    extraction = _parse_response(raw_response)
    return extraction, ANTHROPIC_MODEL


def _parse_response(raw: str) -> DocumentExtraction:
    # Strip markdown fences if model added them anyway
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    try:
        data = json.loads(raw)
        return DocumentExtraction(**data)
    except Exception as e:
        return DocumentExtraction(
            extraction_warnings=[f"Failed to parse AI response: {e}", f"Raw: {raw[:200]}"],
            confidence=0.0,
        )
