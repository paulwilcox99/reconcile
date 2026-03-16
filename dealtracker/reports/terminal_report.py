from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import Optional

console = Console()

STATUS_COLORS = {
    "clean": "green",
    "incomplete": "yellow",
    "over_billed": "red",
    "under_billed": "red",
    "over_paid": "orange3",
    "under_paid": "red",
    "missing_docs": "magenta",
    "disputed": "red",
    "open": "cyan",
    "reconciled": "green",
    "closed": "dim",
}

DOC_TYPE_ORDER = [
    "estimate_request", "estimate", "quote_request", "quote",
    "purchase_order", "invoice", "payment", "receipt", "unknown",
]


def fmt_amount(amount: Optional[float]) -> str:
    if amount is None:
        return "[dim]—[/dim]"
    return f"${amount:,.2f}"


def print_deal_report(deal, documents, reconciliation_result=None):
    customer_name = deal.customer.name if deal.customer else "Unknown"
    status_color = STATUS_COLORS.get(deal.status, "white")

    console.print()
    console.rule(f"[bold]Deal Report[/bold]")
    console.print(
        Panel(
            f"[bold]Reference:[/bold] [cyan]{deal.reference_number}[/cyan]\n"
            f"[bold]Customer:[/bold]  {customer_name}\n"
            f"[bold]Deal:[/bold]      {deal.description}\n"
            f"[bold]Status:[/bold]    [{status_color}]{deal.status.upper()}[/{status_color}]\n"
            f"[bold]Deal ID:[/bold]   {deal.id}",
            title="Deal Summary",
            border_style="blue",
        )
    )

    # Document timeline
    table = Table(
        title="Document Timeline",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("ID", style="dim", width=5)
    table.add_column("Date", width=12)
    table.add_column("Type", width=18)
    table.add_column("Amount", justify="right", width=12)
    table.add_column("Confirmed", width=10)
    table.add_column("File", style="dim")

    sorted_docs = sorted(
        documents,
        key=lambda d: (
            DOC_TYPE_ORDER.index(d.confirmed_doc_type or d.doc_type or "unknown")
            if (d.confirmed_doc_type or d.doc_type or "unknown") in DOC_TYPE_ORDER
            else 99,
            d.confirmed_date or d.ai_extracted_date or "",
        ),
    )

    for doc in sorted_docs:
        doc_type = doc.confirmed_doc_type or doc.doc_type or "unknown"
        amount = doc.confirmed_total_amount if doc.is_confirmed else doc.ai_total_amount
        date = doc.confirmed_date or doc.ai_extracted_date or "—"
        confirmed_str = "[green]Yes[/green]" if doc.is_confirmed else "[yellow]Pending[/yellow]"

        # Highlight discrepant invoices
        row_style = ""
        if reconciliation_result and doc.id in reconciliation_result.invoice_doc_ids:
            if reconciliation_result.invoice_vs_quote_delta and abs(reconciliation_result.invoice_vs_quote_delta) > 0.50:
                row_style = "red"

        table.add_row(
            str(doc.id),
            date,
            _format_doc_type(doc_type),
            fmt_amount(amount),
            confirmed_str,
            doc.file_path,
            style=row_style,
        )

    console.print(table)

    # Reconciliation summary
    if reconciliation_result:
        _print_reconciliation(reconciliation_result)


def _print_reconciliation(result):
    status_color = STATUS_COLORS.get(result.status, "white")
    lines = [
        f"[bold]Agreed (Quote/PO):[/bold]  {fmt_amount(result.agreed_amount)}",
        f"[bold]Invoiced:[/bold]           {fmt_amount(result.invoiced_amount)}",
        f"[bold]Paid:[/bold]               {fmt_amount(result.paid_amount)}",
        "",
        f"[bold]Status:[/bold]             [{status_color}]{result.status.upper().replace('_', ' ')}[/{status_color}]",
    ]

    if result.discrepancies:
        lines.append("")
        lines.append("[bold red]Discrepancies:[/bold red]")
        for d in result.discrepancies:
            lines.append(f"  [red]• {d}[/red]")

    border = "red" if result.has_discrepancy else "green"
    console.print(
        Panel(
            "\n".join(lines),
            title="Reconciliation",
            border_style=border,
        )
    )


def print_deals_table(deals):
    if not deals:
        console.print("[dim]No deals found.[/dim]")
        return

    table = Table(
        title="Deals",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Reference", style="cyan bold", no_wrap=True, width=14)
    table.add_column("Customer", width=14)
    table.add_column("Description", width=22)
    table.add_column("Status", width=10)
    table.add_column("Agreed", justify="right", width=10)

    for deal in deals:
        status_color = STATUS_COLORS.get(deal.status, "white")
        table.add_row(
            deal.reference_number,
            deal.customer.name if deal.customer else "—",
            deal.description[:50] + ("…" if len(deal.description) > 50 else ""),
            f"[{status_color}]{deal.status}[/{status_color}]",
            fmt_amount(deal.agreed_amount),
        )

    console.print(table)


def print_customers_table(customers):
    if not customers:
        console.print("[dim]No customers found.[/dim]")
        return

    table = Table(title="Customers", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Name", width=25)
    table.add_column("Email", width=25)
    table.add_column("Phone", width=15)
    table.add_column("Deals", justify="center", width=6)

    for c in customers:
        table.add_row(
            str(c.id),
            c.name,
            c.email or "—",
            c.phone or "—",
            str(len(c.deals)),
        )

    console.print(table)


def print_reconcile_summary(results: list):
    """Print a summary table of reconciliation results for multiple deals."""
    if not results:
        console.print("[dim]No deals to reconcile.[/dim]")
        return

    table = Table(
        title="Reconciliation Summary",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Reference", style="cyan bold", no_wrap=True, width=14)
    table.add_column("Customer", width=12)
    table.add_column("Description", width=16)
    table.add_column("Agreed", justify="right", width=10)
    table.add_column("Invoiced", justify="right", width=10)
    table.add_column("Paid", justify="right", width=10)
    table.add_column("Status", width=10)

    for deal, result in results:
        status_color = STATUS_COLORS.get(result.status, "white")
        table.add_row(
            deal.reference_number,
            deal.customer.name if deal.customer else "—",
            deal.description[:35] + ("…" if len(deal.description) > 35 else ""),
            fmt_amount(result.agreed_amount),
            fmt_amount(result.invoiced_amount),
            fmt_amount(result.paid_amount),
            f"[{status_color}]{result.status.replace('_', ' ')}[/{status_color}]",
        )

    console.print(table)


def _format_doc_type(doc_type: str) -> str:
    return doc_type.replace("_", " ").title()
