from pathlib import Path

SUPPORTED_EXTENSIONS = {".txt", ".text", ".eml", ".email", ".md", ".csv"}


def is_text_file(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def read_text(file_path: Path) -> str:
    """Read a text file, trying utf-8 then latin-1 fallback."""
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1")
