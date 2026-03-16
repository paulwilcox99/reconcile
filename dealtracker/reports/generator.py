from datetime import datetime
from pathlib import Path

from dealtracker.config import REPORTS_DIR
from dealtracker.reconciliation.engine import reconcile_deal
from dealtracker.reports import html_report, terminal_report
from dealtracker.reports.pdf_report import html_to_pdf


def _report_dir() -> Path:
    d = REPORTS_DIR / datetime.now().strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_deal_report(deal_id: int, session, fmt: str = "terminal", output_dir: Path = None):
    """
    Generate a report for a single deal.
    fmt: "terminal" | "pdf" | "html" | "all"
    """
    from dealtracker.models import Deal

    deal = session.get(Deal, deal_id)
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")

    customer = deal.customer
    documents = sorted(
        deal.documents,
        key=lambda d: d.confirmed_date or d.ai_extracted_date or "",
    )
    result = reconcile_deal(deal_id, session)

    out_dir = Path(output_dir) if output_dir else _report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = f"deal_{deal_id}_{datetime.now().strftime('%H%M%S')}"

    paths = {}

    if fmt in ("terminal", "all"):
        terminal_report.print_deal_report(deal, documents, result)

    if fmt in ("html", "pdf", "all"):
        html_path = out_dir / f"{slug}.html"
        html_report.render_deal_report(deal, customer, documents, result, html_path)
        paths["html"] = html_path
        print(f"  HTML report: {html_path}")

    if fmt in ("pdf", "all"):
        pdf_path = out_dir / f"{slug}.pdf"
        html_to_pdf(paths["html"], pdf_path)
        paths["pdf"] = pdf_path
        print(f"  PDF  report: {pdf_path}")

    return paths


def generate_full_report(session, fmt: str = "terminal", output_dir: Path = None,
                         customer_id: int = None):
    """
    Generate a report covering all deals (or all deals for a customer).
    """
    from dealtracker.models import Deal, Customer

    query = session.query(Deal)
    if customer_id:
        query = query.filter(Deal.customer_id == customer_id)
    deals = query.order_by(Deal.customer_id, Deal.id).all()

    entries = []
    for deal in deals:
        result = reconcile_deal(deal.id, session)
        documents = sorted(
            deal.documents,
            key=lambda d: d.confirmed_date or d.ai_extracted_date or "",
        )
        entries.append({
            "deal": deal,
            "customer": deal.customer,
            "documents": documents,
            "reconciliation": result,
        })

    out_dir = Path(output_dir) if output_dir else _report_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"full_{datetime.now().strftime('%H%M%S')}"
    paths = {}

    if fmt in ("terminal", "all"):
        for entry in entries:
            terminal_report.print_deal_report(
                entry["deal"], entry["documents"], entry["reconciliation"]
            )

    if fmt in ("html", "pdf", "all"):
        html_path = out_dir / f"{slug}.html"
        html_report.render_full_report(entries, html_path)
        paths["html"] = html_path
        print(f"  HTML report: {html_path}")

    if fmt in ("pdf", "all"):
        pdf_path = out_dir / f"{slug}.pdf"
        html_to_pdf(paths["html"], pdf_path)
        paths["pdf"] = pdf_path
        print(f"  PDF  report: {pdf_path}")

    return paths
