import json
from pathlib import Path
from dealtracker.ai.schemas import DocumentExtraction, SYSTEM_PROMPT
from dealtracker.config import OPENAI_API_KEY, OPENAI_MODEL


def extract_from_text(text: str) -> tuple[DocumentExtraction, str]:
    """Use GPT to extract from plain text (fallback when Claude unavailable)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Please extract information from this document:\n\n{text}"},
        ],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    extraction = _parse_response(raw)
    return extraction, OPENAI_MODEL


def extract_from_image(base64_data: str, media_type: str) -> tuple[DocumentExtraction, str]:
    """Use GPT-4o Vision to extract from an image (base64-encoded)."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please extract information from this document image:",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64_data}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    extraction = _parse_response(raw)
    return extraction, OPENAI_MODEL


def _parse_response(raw: str) -> DocumentExtraction:
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
