import shutil
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from dealtracker.ai import dispatcher
from dealtracker.ai.schemas import DOC_TYPES, DOC_TYPE_LABELS
from dealtracker.database import get_session
from dealtracker.models import Customer, Deal, Document
from dealtracker.parsers import image_parser, text_parser
from dealtracker.utils import make_slug, generate_reference_number

console = Console()

SUPPORTED_EXTENSIONS = (
    {".pdf"}
    | image_parser.SUPPORTED_EXTENSIONS
    | text_parser.SUPPORTED_EXTENSIONS
)


@click.group("doc")
def doc_group():
    """Manage documents."""


@doc_group.command("add")
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--provider",
    type=click.Choice(["auto", "openai", "anthropic"]),
    default="auto",
    show_default=True,
    help="AI provider to use for extraction",
)
def doc_add(file_path, provider):
    """Ingest a document: AI extracts info, you confirm and link to a deal."""
    src = Path(file_path).resolve()

    if src.suffix.lower() not in SUPPORTED_EXTENSIONS and src.suffix.lower() != ".pdf":
        console.print(f"[red]Unsupported file type: {src.suffix}[/red]")
        raise SystemExit(1)

    file_type = dispatcher.detect_file_type(src)
    if file_type == "unknown":
        console.print(f"[red]Could not determine file type for: {src.name}[/red]")
        raise SystemExit(1)

    console.print(f"\n[bold]Ingesting:[/bold] {src.name}  [dim]({file_type})[/dim]")

    # Copy to staging
    from dealtracker.config import DOCUMENTS_DIR
    staging = DOCUMENTS_DIR / "unassigned"
    staging.mkdir(parents=True, exist_ok=True)
    dest = _unique_path(staging / src.name)
    shutil.copy2(src, dest)

    # AI extraction
    console.print("[cyan]Running AI extraction…[/cyan]")
    try:
        extraction, ai_provider, ai_model = dispatcher.run(src, provider=provider)
    except Exception as e:
        console.print(f"[red]AI extraction failed: {e}[/red]")
        dest.unlink(missing_ok=True)
        raise SystemExit(1)

    # Show extraction results
    _show_extraction(extraction, ai_provider, ai_model)

    # Let user edit extracted fields
    confirmed = _confirm_fields(extraction)
    if confirmed is None:
        console.print("[yellow]Document rejected — removed from staging.[/yellow]")
        dest.unlink(missing_ok=True)
        return

    # Resolve which deal this belongs to
    with get_session() as session:
        deal = _resolve_deal(session, confirmed)
        if deal is None:
            console.print("[yellow]No deal selected — document not saved.[/yellow]")
            dest.unlink(missing_ok=True)
            return

        # Move file into deal's directory
        dest = _move_to_deal(dest, deal, session)

        # Save document
        doc = Document(
            deal_id=deal.id,
            customer_id=deal.customer_id,
            file_path=str(dest),
            original_filename=src.name,
            file_type=file_type,
            doc_type=confirmed.document_type,
            # AI raw fields
            ai_extracted_date=extraction.document_date,
            ai_customer_name=extraction.customer_name,
            ai_deal_description=extraction.deal_description,
            ai_doc_type=extraction.document_type,
            ai_total_amount=extraction.total_amount_usd,
            ai_currency=extraction.currency_detected,
            ai_notes=extraction.notes,
            ai_confidence=extraction.confidence,
            ai_raw_response=str(extraction.model_dump()),
            # Confirmed fields
            confirmed_date=confirmed.document_date,
            confirmed_customer_name=confirmed.customer_name,
            confirmed_deal_description=confirmed.deal_description,
            confirmed_doc_type=confirmed.document_type,
            confirmed_total_amount=confirmed.total_amount_usd,
            confirmed_notes=confirmed.notes,
            is_confirmed=True,
            confirmed_at=datetime.utcnow(),
            ai_provider=ai_provider,
            ai_model=ai_model,
        )
        session.add(doc)
        session.flush()

        # Update deal agreed_amount when a quote or PO is added
        if confirmed.document_type in ("quote", "purchase_order") and confirmed.total_amount_usd:
            old = deal.agreed_amount
            deal.agreed_amount = confirmed.total_amount_usd
            console.print(
                f"[green]Agreed amount updated:[/green] "
                f"${old or 0:,.2f} → ${confirmed.total_amount_usd:,.2f}"
            )

        console.print(
            f"\n[bold green]Saved[/bold green]  "
            f"doc ID {doc.id}  →  deal [cyan]{deal.reference_number}[/cyan]  "
            f"({deal.description[:50]})"
        )


@doc_group.command("list")
@click.option("--deal", "deal_ref", default=None, help="Filter by deal ID or reference")
@click.option("--unconfirmed", is_flag=True, help="Show only unconfirmed documents")
def doc_list(deal_ref, unconfirmed):
    """List documents."""
    with get_session() as session:
        query = session.query(Document)
        if deal_ref:
            from dealtracker.commands.deals import _lookup_deal
            deal = _lookup_deal(session, deal_ref)
            if not deal:
                console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
                raise SystemExit(1)
            query = query.filter(Document.deal_id == deal.id)
        if unconfirmed:
            query = query.filter(Document.is_confirmed == False)
        docs = query.order_by(Document.ingested_at.desc()).all()

        if not docs:
            console.print("[dim]No documents found.[/dim]")
            return

        table = Table(title="Documents", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Deal Ref", width=14)
        table.add_column("Date", width=12)
        table.add_column("Type", width=18)
        table.add_column("Amount", justify="right", width=12)
        table.add_column("Confirmed", width=10)
        table.add_column("File")

        for doc in docs:
            ref = doc.deal.reference_number if doc.deal else "—"
            table.add_row(
                str(doc.id),
                ref,
                doc.confirmed_date or doc.ai_extracted_date or "—",
                (doc.confirmed_doc_type or doc.doc_type or "unknown").replace("_", " ").title(),
                f"${doc.confirmed_total_amount:,.2f}" if doc.confirmed_total_amount else "—",
                "[green]Yes[/green]" if doc.is_confirmed else "[yellow]No[/yellow]",
                doc.original_filename,
            )
        console.print(table)


@doc_group.command("show")
@click.argument("doc_id", type=int)
def doc_show(doc_id):
    """Show full document detail."""
    with get_session() as session:
        doc = session.get(Document, doc_id)
        if not doc:
            console.print(f"[red]Document {doc_id} not found.[/red]")
            raise SystemExit(1)

        ref = doc.deal.reference_number if doc.deal else "—"
        console.print(
            Panel(
                f"[bold]ID:[/bold]          {doc.id}\n"
                f"[bold]Deal Ref:[/bold]    {ref}\n"
                f"[bold]File:[/bold]        {doc.file_path}\n"
                f"[bold]Type:[/bold]        {doc.file_type}\n"
                f"[bold]Doc Type:[/bold]    {doc.confirmed_doc_type or doc.doc_type or '—'}\n"
                f"[bold]Date:[/bold]        {doc.confirmed_date or doc.ai_extracted_date or '—'}\n"
                f"[bold]Customer:[/bold]    {doc.confirmed_customer_name or doc.ai_customer_name or '—'}\n"
                f"[bold]Description:[/bold] {doc.confirmed_deal_description or doc.ai_deal_description or '—'}\n"
                f"[bold]Amount:[/bold]      {'${:,.2f}'.format(doc.confirmed_total_amount) if doc.confirmed_total_amount else '—'}\n"
                f"[bold]Confirmed:[/bold]   {'Yes' if doc.is_confirmed else 'No'}\n"
                f"[bold]AI Provider:[/bold] {doc.ai_provider or '—'}  ({doc.ai_model or '—'})\n"
                f"[bold]Confidence:[/bold]  {doc.ai_confidence or '—'}\n"
                f"[bold]Notes:[/bold]       {doc.confirmed_notes or doc.ai_notes or '—'}",
                title=f"Document {doc.id}: {doc.original_filename}",
                border_style="blue",
            )
        )


@doc_group.command("reprocess")
@click.argument("doc_id", type=int)
@click.option("--provider", type=click.Choice(["auto", "openai", "anthropic"]), default="auto")
def doc_reprocess(doc_id, provider):
    """Re-run AI extraction on an existing document and re-confirm fields."""
    with get_session() as session:
        doc = session.get(Document, doc_id)
        if not doc:
            console.print(f"[red]Document {doc_id} not found.[/red]")
            raise SystemExit(1)

        file_path = Path(doc.file_path)
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            raise SystemExit(1)

        console.print(f"[cyan]Re-processing: {doc.original_filename}…[/cyan]")
        extraction, ai_provider, ai_model = dispatcher.run(file_path, provider=provider)
        _show_extraction(extraction, ai_provider, ai_model)

        confirmed = _confirm_fields(extraction)
        if confirmed is None:
            console.print("[yellow]Aborted.[/yellow]")
            return

        doc.ai_extracted_date = extraction.document_date
        doc.ai_customer_name = extraction.customer_name
        doc.ai_deal_description = extraction.deal_description
        doc.ai_doc_type = extraction.document_type
        doc.ai_total_amount = extraction.total_amount_usd
        doc.ai_currency = extraction.currency_detected
        doc.ai_notes = extraction.notes
        doc.ai_confidence = extraction.confidence
        doc.ai_raw_response = str(extraction.model_dump())
        doc.ai_provider = ai_provider
        doc.ai_model = ai_model
        doc.confirmed_date = confirmed.document_date
        doc.confirmed_customer_name = confirmed.customer_name
        doc.confirmed_deal_description = confirmed.deal_description
        doc.confirmed_doc_type = confirmed.document_type
        doc.confirmed_total_amount = confirmed.total_amount_usd
        doc.confirmed_notes = confirmed.notes
        doc.is_confirmed = True
        doc.confirmed_at = datetime.utcnow()

        console.print(f"[green]Document {doc_id} reprocessed.[/green]")


# ─── Interactive helpers ───────────────────────────────────────────────────────

def _show_extraction(extraction, provider: str, model: str):
    table = Table(title="AI Extraction Result", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Field", style="bold", width=22)
    table.add_column("Value")

    table.add_row("Provider / Model", f"{provider} / {model}")
    table.add_row("Confidence", f"{extraction.confidence:.0%}")
    table.add_row("Document Type", DOC_TYPE_LABELS.get(extraction.document_type, extraction.document_type))
    table.add_row("Date", extraction.document_date or "[dim]—[/dim]")
    table.add_row("Customer Name", extraction.customer_name or "[dim]—[/dim]")
    table.add_row("Deal Description", extraction.deal_description or "[dim]—[/dim]")
    table.add_row("Deal Reference Found", extraction.deal_reference or "[dim]none[/dim]")
    table.add_row(
        "Total Amount (USD)",
        f"${extraction.total_amount_usd:,.2f}" if extraction.total_amount_usd else "[dim]—[/dim]",
    )
    table.add_row("Notes", extraction.notes or "[dim]—[/dim]")

    if extraction.extraction_warnings:
        table.add_row(
            "[yellow]Warnings[/yellow]",
            "\n".join(f"• {w}" for w in extraction.extraction_warnings),
        )
    console.print(table)


def _confirm_fields(extraction):
    """
    Show extracted fields and let user accept, edit, or reject.
    Returns confirmed DocumentExtraction or None (reject).
    """
    from dealtracker.ai.schemas import DocumentExtraction

    console.print("\n[bold]Review extracted fields:[/bold]")
    console.print("  [a] Accept all   [e] Edit fields   [r] Reject document")
    choice = click.prompt("Choice", default="a").strip().lower()

    if choice == "r":
        return None
    if choice == "a":
        return extraction
    if choice == "e":
        return _edit_fields(extraction)

    console.print("[yellow]Unknown choice — accepting as-is.[/yellow]")
    return extraction


def _edit_fields(extraction):
    """Field-by-field editing."""
    from dealtracker.ai.schemas import DocumentExtraction

    doc_type_choices = list(DOC_TYPES.__args__)

    console.print("\n[dim]Press Enter to keep the current value.[/dim]")
    date = click.prompt("  Date", default=extraction.document_date or "", show_default=True).strip() or None
    customer = click.prompt("  Customer name", default=extraction.customer_name or "", show_default=True).strip() or None
    description = click.prompt("  Deal description", default=extraction.deal_description or "", show_default=True).strip() or None

    console.print(f"  Doc types: {', '.join(doc_type_choices)}")
    doc_type = click.prompt("  Document type", default=extraction.document_type, show_default=True).strip()
    if doc_type not in doc_type_choices:
        console.print(f"[yellow]  Invalid — keeping '{extraction.document_type}'[/yellow]")
        doc_type = extraction.document_type

    amt_str = click.prompt(
        "  Total amount (USD)",
        default=str(extraction.total_amount_usd or ""),
        show_default=True,
    ).strip()
    try:
        amount = float(amt_str) if amt_str else None
    except ValueError:
        console.print("[yellow]  Invalid amount — keeping original.[/yellow]")
        amount = extraction.total_amount_usd

    notes = click.prompt("  Notes", default=extraction.notes or "", show_default=True).strip() or None

    return DocumentExtraction(
        document_date=date,
        customer_name=customer,
        deal_description=description,
        deal_reference=extraction.deal_reference,
        document_type=doc_type,
        total_amount_usd=amount,
        currency_detected="USD",
        notes=notes,
        confidence=extraction.confidence,
        extraction_warnings=extraction.extraction_warnings,
    )


def _resolve_deal(session, extraction) -> Deal | None:
    """
    Find which deal this document belongs to.

    Priority:
      1. AI found a deal_reference → look it up, ask to confirm
      2. No reference found → show deal list and let user select or create
    """
    all_deals = session.query(Deal).order_by(Deal.reference_number).all()

    # --- Try reference number from AI extraction ---
    if extraction.deal_reference:
        ref = extraction.deal_reference.strip().upper()
        deal = session.query(Deal).filter_by(reference_number=ref).first()
        if deal:
            console.print(
                f"\n[green]Deal reference found:[/green] "
                f"[cyan]{deal.reference_number}[/cyan]  {deal.description}"
            )
            if click.confirm("  Link document to this deal?", default=True):
                return deal
            # User said no — fall through to manual selection
        else:
            console.print(
                f"\n[yellow]Reference '{extraction.deal_reference}' not found in database.[/yellow]"
            )

    # --- Manual selection ---
    return _pick_deal(session, all_deals, extraction)


def _pick_deal(session, deals: list, extraction) -> Deal | None:
    """Show a numbered list of deals and let the user pick one or create new."""
    console.print()

    if deals:
        table = Table(title="Existing Deals", box=box.SIMPLE, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Reference", width=14)
        table.add_column("Customer", width=20)
        table.add_column("Description", width=40)
        table.add_column("Status", width=10)

        for i, deal in enumerate(deals, 1):
            cust_name = deal.customer.name if deal.customer else "—"
            table.add_row(
                str(i),
                deal.reference_number,
                cust_name,
                deal.description[:45] + ("…" if len(deal.description) > 45 else ""),
                deal.status,
            )
        console.print(table)
        console.print("  [bold][n][/bold] Create new deal   [bold][x][/bold] Cancel")
        prompt_text = f"Select deal number, 'n' to create new, or 'x' to cancel"
    else:
        console.print("  [dim]No existing deals.[/dim]")
        console.print("  [bold][n][/bold] Create new deal   [bold][x][/bold] Cancel")
        prompt_text = "Enter 'n' to create a deal or 'x' to cancel"

    while True:
        raw = click.prompt(prompt_text).strip().lower()

        if raw == "x":
            return None

        if raw == "n":
            return _create_deal(session, extraction)

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(deals):
                chosen = deals[idx]
                console.print(
                    f"[green]Linked to:[/green] [cyan]{chosen.reference_number}[/cyan]  {chosen.description}"
                )
                return chosen
            console.print(f"[red]  Invalid number. Enter 1–{len(deals)}, 'n', or 'x'.[/red]")
        else:
            console.print("[red]  Enter a number, 'n', or 'x'.[/red]")


def _create_deal(session, extraction) -> Deal | None:
    """Interactively create a new deal, pre-filling from extraction where possible."""
    console.print("\n[bold]Create new deal[/bold]")

    # Customer
    customer_name = click.prompt(
        "  Customer name",
        default=extraction.customer_name or "",
        show_default=bool(extraction.customer_name),
    ).strip()
    if not customer_name:
        console.print("[red]  Customer name required.[/red]")
        return None

    # Find or create customer
    from dealtracker.utils import fuzzy_match_score
    all_customers = session.query(Customer).all()
    matched_customer = None
    if all_customers:
        best = max(all_customers, key=lambda c: fuzzy_match_score(customer_name, c.name))
        score = fuzzy_match_score(customer_name, best.name)
        if score >= 0.80:
            console.print(f"  [dim]Existing customer match:[/dim] {best.name} ({score:.0%})")
            if click.confirm(f"  Use existing customer '{best.name}'?", default=True):
                matched_customer = best

    if not matched_customer:
        slug = make_slug(customer_name)
        existing = session.query(Customer).filter_by(slug=slug).first()
        matched_customer = existing or Customer(name=customer_name, slug=slug)
        if not matched_customer.id:
            session.add(matched_customer)
            session.flush()
            console.print(f"  [green]New customer:[/green] {matched_customer.name} (ID: {matched_customer.id})")

    # Description
    description = click.prompt(
        "  Job description",
        default=extraction.deal_description or "",
        show_default=bool(extraction.deal_description),
    ).strip()
    if not description:
        console.print("[red]  Description required.[/red]")
        return None

    # Reference number
    auto_ref = generate_reference_number(session)
    ref = click.prompt("  Deal reference number", default=auto_ref, show_default=True).strip().upper()
    if session.query(Deal).filter_by(reference_number=ref).first():
        console.print(f"[red]  Reference '{ref}' already exists.[/red]")
        return None

    deal = Deal(
        reference_number=ref,
        customer_id=matched_customer.id,
        description=description,
        description_slug=make_slug(description),
        status="open",
    )
    session.add(deal)
    session.flush()
    console.print(
        f"  [green]Deal created:[/green] [cyan]{deal.reference_number}[/cyan]  {deal.description}"
    )
    return deal


def _move_to_deal(src: Path, deal: Deal, session) -> Path:
    """Move a staged file into data/documents/{customer_slug}/{deal_ref}/"""
    from dealtracker.config import DOCUMENTS_DIR
    customer = deal.customer or session.get(Customer, deal.customer_id)
    cust_slug = make_slug(customer.name) if customer else "unknown"
    dest_dir = DOCUMENTS_DIR / cust_slug / deal.reference_number
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_path(dest_dir / src.name)
    if src != dest:
        shutil.move(str(src), str(dest))
    return dest


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1
