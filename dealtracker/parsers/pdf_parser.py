from pathlib import Path


def extract_text(file_path: Path) -> str:
    """Extract text from a PDF. Returns empty string if pdfplumber unavailable or fails."""
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        with pdfplumber.open(file_path) as pdf:
            parts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
            return "\n".join(parts)
    except Exception:
        return ""


def is_text_rich(file_path: Path, threshold: int = 200) -> bool:
    """Return True if the PDF contains enough extractable text for Claude to process."""
    return len(extract_text(file_path)) >= threshold
