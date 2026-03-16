import base64
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp"}


def is_image(file_path: Path) -> bool:
    return file_path.suffix.lower() in SUPPORTED_EXTENSIONS


def to_base64(file_path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image file."""
    ext = file_path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    media_type = media_type_map.get(ext, "image/jpeg")
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, media_type


def pdf_page_to_base64(file_path: Path, page_num: int = 0) -> tuple[str, str] | None:
    """Convert a specific PDF page to a base64 PNG for vision models."""
    try:
        import pdfplumber
        from PIL import Image
        import io

        with pdfplumber.open(file_path) as pdf:
            if page_num >= len(pdf.pages):
                return None
            page = pdf.pages[page_num]
            img = page.to_image(resolution=150)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            data = base64.b64encode(buf.read()).decode("utf-8")
            return data, "image/png"
    except Exception:
        return None
