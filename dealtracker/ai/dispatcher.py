from pathlib import Path
from dealtracker.ai.schemas import DocumentExtraction
from dealtracker.parsers import pdf_parser, image_parser, text_parser

PDF_TEXT_THRESHOLD = 200  # characters; below this → treat as scanned, use vision


def detect_file_type(file_path: Path) -> str:
    """Return canonical file type: pdf | image | text."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in image_parser.SUPPORTED_EXTENSIONS:
        return "image"
    if ext in text_parser.SUPPORTED_EXTENSIONS:
        return "text"
    # Fallback: try to read as text
    try:
        file_path.read_text(encoding="utf-8")
        return "text"
    except Exception:
        return "unknown"


def run(
    file_path: Path,
    provider: str = "auto",
) -> tuple[DocumentExtraction, str, str]:
    """
    Dispatch a file to the appropriate AI handler.

    Returns:
        (DocumentExtraction, provider_used, model_used)

    provider options: "auto" | "openai" | "anthropic"
    """
    file_type = detect_file_type(file_path)

    if file_type == "unknown":
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    # --- PDF ---
    if file_type == "pdf":
        text = pdf_parser.extract_text(file_path)
        if len(text) >= PDF_TEXT_THRESHOLD and provider != "openai":
            # Text-rich PDF → Claude
            from dealtracker.ai import claude_handler
            extraction, model = claude_handler.extract(text)
            return extraction, "anthropic", model
        else:
            # Scanned / low-text PDF → GPT-4o Vision (first page)
            from dealtracker.ai import openai_handler
            from dealtracker.parsers import image_parser as img
            result = img.pdf_page_to_base64(file_path, page_num=0)
            if result is None:
                # Vision conversion failed; try text anyway
                if text:
                    extraction, model = openai_handler.extract_from_text(text)
                else:
                    raise RuntimeError("Could not extract content from PDF")
            else:
                b64, media_type = result
                extraction, model = openai_handler.extract_from_image(b64, media_type)
            return extraction, "openai", model

    # --- Image ---
    if file_type == "image":
        if provider == "anthropic":
            # Claude vision via base64
            b64, media_type = image_parser.to_base64(file_path)
            extraction, model = _claude_vision(b64, media_type)
            return extraction, "anthropic", model
        else:
            from dealtracker.ai import openai_handler
            b64, media_type = image_parser.to_base64(file_path)
            extraction, model = openai_handler.extract_from_image(b64, media_type)
            return extraction, "openai", model

    # --- Text / email ---
    if file_type == "text":
        text = text_parser.read_text(file_path)
        if provider == "openai":
            from dealtracker.ai import openai_handler
            extraction, model = openai_handler.extract_from_text(text)
            return extraction, "openai", model
        else:
            from dealtracker.ai import claude_handler
            extraction, model = claude_handler.extract(text)
            return extraction, "anthropic", model

    raise ValueError(f"Unhandled file type: {file_type}")


def _claude_vision(base64_data: str, media_type: str) -> tuple[DocumentExtraction, str]:
    """Send image to Claude via vision (Anthropic messages API)."""
    from dealtracker.ai.schemas import SYSTEM_PROMPT, DocumentExtraction
    from dealtracker.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
    import json

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
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data,
                        },
                    },
                    {"type": "text", "text": "Please extract information from this document image:"},
                ],
            }
        ],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    try:
        data = json.loads(raw)
        return DocumentExtraction(**data), ANTHROPIC_MODEL
    except Exception as e:
        return DocumentExtraction(
            extraction_warnings=[f"Parse error: {e}"],
            confidence=0.0,
        ), ANTHROPIC_MODEL
