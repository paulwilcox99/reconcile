from dataclasses import dataclass, field
from typing import Optional
import json

from dealtracker.config import RECONCILIATION_TOLERANCE_USD


@dataclass
class ReconciliationResult:
    deal_id: int
    agreed_amount: Optional[float]
    invoiced_amount: float
    paid_amount: float

    quote_doc_ids: list[int] = field(default_factory=list)
    invoice_doc_ids: list[int] = field(default_factory=list)
    payment_doc_ids: list[int] = field(default_factory=list)

    invoice_vs_quote_delta: Optional[float] = None
    payment_vs_invoice_delta: Optional[float] = None

    discrepancies: list[str] = field(default_factory=list)
    status: str = "incomplete"

    @property
    def has_discrepancy(self) -> bool:
        return len(self.discrepancies) > 0

    def discrepancy_summary(self) -> str:
        return "; ".join(self.discrepancies) if self.discrepancies else "None"


def reconcile_deal(deal_id: int, session) -> ReconciliationResult:
    """
    Compute reconciliation for a deal given a live session.
    Only uses confirmed documents.
    """
    from dealtracker.models import Document

    docs = (
        session.query(Document)
        .filter(Document.deal_id == deal_id, Document.is_confirmed == True)
        .all()
    )

    quote_docs = [d for d in docs if d.confirmed_doc_type in ("quote", "purchase_order")]
    invoice_docs = [d for d in docs if d.confirmed_doc_type == "invoice"]
    payment_docs = [d for d in docs if d.confirmed_doc_type == "payment"]
    receipt_docs = [d for d in docs if d.confirmed_doc_type == "receipt"]

    agreed = _select_agreed_amount(quote_docs)
    invoiced = sum(d.confirmed_total_amount or 0.0 for d in invoice_docs)

    # A receipt is our confirmation of receiving a payment — not an additional payment.
    # Use payment docs for the paid total; fall back to receipts only if no payment docs exist.
    if payment_docs:
        paid = sum(d.confirmed_total_amount or 0.0 for d in payment_docs)
        payment_docs_used = payment_docs
    else:
        paid = sum(d.confirmed_total_amount or 0.0 for d in receipt_docs)
        payment_docs_used = receipt_docs

    invoice_delta: Optional[float] = None
    payment_delta: Optional[float] = None
    discrepancies = []
    tol = RECONCILIATION_TOLERANCE_USD

    if agreed is None and invoice_docs:
        discrepancies.append(
            "MISSING_QUOTE: invoices exist but no confirmed quote or purchase order found"
        )
    if agreed is not None and invoice_docs:
        invoice_delta = round(invoiced - agreed, 2)
        if abs(invoice_delta) > tol:
            direction = "over" if invoice_delta > 0 else "under"
            discrepancies.append(
                f"INVOICE_MISMATCH: billed ${invoiced:,.2f} vs agreed ${agreed:,.2f} "
                f"({direction}-billed by ${abs(invoice_delta):,.2f})"
            )

    if invoice_docs and payment_docs_used:
        payment_delta = round(paid - invoiced, 2)
        if abs(payment_delta) > tol:
            direction = "over" if payment_delta > 0 else "under"
            discrepancies.append(
                f"PAYMENT_MISMATCH: paid ${paid:,.2f} vs invoiced ${invoiced:,.2f} "
                f"({direction}-paid by ${abs(payment_delta):,.2f})"
            )

    if payment_docs_used and not invoice_docs:
        discrepancies.append(
            "MISSING_INVOICE: payment received but no invoice on record"
        )

    status = _determine_status(discrepancies, docs, agreed, invoice_docs, payment_docs_used)

    return ReconciliationResult(
        deal_id=deal_id,
        agreed_amount=agreed,
        invoiced_amount=invoiced,
        paid_amount=paid,
        quote_doc_ids=[d.id for d in quote_docs],
        invoice_doc_ids=[d.id for d in invoice_docs],
        payment_doc_ids=[d.id for d in payment_docs_used],
        invoice_vs_quote_delta=invoice_delta,
        payment_vs_invoice_delta=payment_delta,
        discrepancies=discrepancies,
        status=status,
    )


def _select_agreed_amount(quote_docs: list) -> Optional[float]:
    """Return the total amount from the most recent confirmed quote/PO."""
    if not quote_docs:
        return None

    # Prefer quote over purchase_order; within same type, prefer most recent by date
    def sort_key(d):
        type_priority = 0 if d.confirmed_doc_type == "quote" else 1
        date_str = d.confirmed_date or ""
        return (type_priority, date_str)

    sorted_docs = sorted(quote_docs, key=sort_key)
    # Use the last (most recent) quote
    best = sorted_docs[-1]
    return best.confirmed_total_amount


def _determine_status(
    discrepancies: list[str],
    all_docs: list,
    agreed: Optional[float],
    invoice_docs: list,
    payment_docs: list,
) -> str:
    if not discrepancies:
        if invoice_docs and payment_docs and agreed is not None:
            return "clean"
        return "incomplete"

    statuses = []
    for d in discrepancies:
        if d.startswith("INVOICE_MISMATCH"):
            if "over-billed" in d:
                statuses.append("over_billed")
            else:
                statuses.append("under_billed")
        elif d.startswith("PAYMENT_MISMATCH"):
            if "over-paid" in d:
                statuses.append("over_paid")
            else:
                statuses.append("under_paid")
        elif "MISSING" in d:
            statuses.append("missing_docs")

    # Return the most severe
    priority = ["over_billed", "under_billed", "over_paid", "under_paid", "missing_docs"]
    for p in priority:
        if p in statuses:
            return p
    return "disputed"


def save_snapshot(result: ReconciliationResult, session) -> "ReconciliationSnapshot":
    """Persist a ReconciliationResult as a snapshot row."""
    from dealtracker.models import ReconciliationSnapshot

    snapshot = ReconciliationSnapshot(
        deal_id=result.deal_id,
        agreed_amount=result.agreed_amount,
        invoiced_amount=result.invoiced_amount,
        paid_amount=result.paid_amount,
        quote_doc_ids=json.dumps(result.quote_doc_ids),
        invoice_doc_ids=json.dumps(result.invoice_doc_ids),
        payment_doc_ids=json.dumps(result.payment_doc_ids),
        invoice_vs_quote_delta=result.invoice_vs_quote_delta,
        payment_vs_invoice_delta=result.payment_vs_invoice_delta,
        has_discrepancy=result.has_discrepancy,
        discrepancy_notes=result.discrepancy_summary(),
        status=result.status,
    )
    session.add(snapshot)
    return snapshot
