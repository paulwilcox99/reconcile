from pathlib import Path


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Convert an HTML report to PDF using weasyprint (fallback: reportlab)."""
    try:
        return _weasyprint(html_path, pdf_path)
    except ImportError:
        return _reportlab_fallback(html_path, pdf_path)


def _weasyprint(html_path: Path, pdf_path: Path) -> Path:
    from weasyprint import HTML
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    return pdf_path


def _reportlab_fallback(html_path: Path, pdf_path: Path) -> Path:
    """Minimal reportlab fallback — strips HTML and renders plain text."""
    import re
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch

    html_content = html_path.read_text(encoding="utf-8")
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()

    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER,
                            leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("DealTracker Report", styles["Title"]), Spacer(1, 12)]

    # Split into paragraphs on double spaces / sentence breaks
    for chunk in text.split("  "):
        chunk = chunk.strip()
        if chunk:
            story.append(Paragraph(chunk, styles["Normal"]))
            story.append(Spacer(1, 4))

    doc.build(story)
    return pdf_path
