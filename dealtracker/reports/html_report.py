from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def render_deal_report(deal, customer, documents, reconciliation, output_path: Path) -> Path:
    env = _env()
    template = env.get_template("report_deal.html.j2")

    discrepant_invoice_ids = set()
    if reconciliation and reconciliation.has_discrepancy:
        discrepant_invoice_ids = set(reconciliation.invoice_doc_ids)

    # Attach full_path to docs for links
    for doc in documents:
        doc.full_path = str(Path(doc.file_path).resolve())

    html = template.render(
        deal=deal,
        customer=customer,
        documents=documents,
        reconciliation=reconciliation,
        discrepant_invoice_ids=discrepant_invoice_ids,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path


def render_full_report(entries: list, output_path: Path) -> Path:
    """
    entries: list of dicts with keys: deal, customer, documents, reconciliation
    """
    env = _env()
    template = env.get_template("report_full.html.j2")

    for entry in entries:
        for doc in entry["documents"]:
            doc.full_path = str(Path(doc.file_path).resolve())

    html = template.render(
        deals=entries,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path
