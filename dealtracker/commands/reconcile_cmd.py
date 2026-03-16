import click
from rich.console import Console
from dealtracker.database import get_session
from dealtracker.models import Deal
from dealtracker.reconciliation.engine import reconcile_deal, save_snapshot
from dealtracker.reports.terminal_report import print_reconcile_summary, _print_reconciliation

console = Console()


@click.group("reconcile")
def reconcile_group():
    """Reconcile deal amounts and flag discrepancies."""


@reconcile_group.command("check")
@click.argument("deal_ref")
@click.option("--save", is_flag=True, help="Save snapshot to database")
@click.option("--verbose", "-v", is_flag=True)
def reconcile_check(deal_ref, save, verbose):
    """Run reconciliation on a single deal. Accepts deal ID or reference (e.g. JOB-2025-001)."""
    from dealtracker.commands.deals import _lookup_deal
    with get_session() as session:
        deal = _lookup_deal(session, deal_ref)
        if not deal:
            console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
            raise SystemExit(1)

        result = reconcile_deal(deal.id, session)

        console.print(f"\n[bold]Reconciliation:[/bold] [{deal.reference_number}] {deal.description}")
        _print_reconciliation(result)

        if verbose and result.discrepancies:
            console.print("\n[bold]Document IDs used:[/bold]")
            console.print(f"  Quote/PO:  {result.quote_doc_ids}")
            console.print(f"  Invoices:  {result.invoice_doc_ids}")
            console.print(f"  Payments:  {result.payment_doc_ids}")

        if save:
            save_snapshot(result, session)
            console.print("[dim]Snapshot saved.[/dim]")

        # Update deal status
        if result.status in ("clean",):
            deal.status = "reconciled"
        elif result.has_discrepancy:
            deal.status = "disputed"


@reconcile_group.command("check-all")
@click.option("--save", is_flag=True, help="Save all snapshots to database")
@click.option("--only-issues", is_flag=True, help="Only show deals with discrepancies")
def reconcile_check_all(save, only_issues):
    """Run reconciliation on all open deals."""
    with get_session() as session:
        deals = session.query(Deal).filter(Deal.status.in_(["open", "incomplete", "disputed"])).all()
        if not deals:
            console.print("[dim]No open deals found.[/dim]")
            return

        results = []
        for deal in deals:
            result = reconcile_deal(deal.id, session)
            if only_issues and not result.has_discrepancy:
                continue
            results.append((deal, result))
            if save:
                save_snapshot(result, session)
                if result.status in ("clean",):
                    deal.status = "reconciled"
                elif result.has_discrepancy:
                    deal.status = "disputed"

        print_reconcile_summary(results)
        if save:
            console.print("[dim]All snapshots saved.[/dim]")


@reconcile_group.command("summary")
def reconcile_summary():
    """Show reconciliation overview for all deals."""
    with get_session() as session:
        deals = session.query(Deal).order_by(Deal.customer_id, Deal.id).all()
        results = []
        for deal in deals:
            result = reconcile_deal(deal.id, session)
            results.append((deal, result))
        print_reconcile_summary(results)
