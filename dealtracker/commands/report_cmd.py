import click
from pathlib import Path
from rich.console import Console
from dealtracker.database import get_session

console = Console()


@click.group("report")
def report_group():
    """Generate deal reports."""


@report_group.command("generate")
@click.option("--deal", "deal_ref", default=None, help="Deal ID or reference (e.g. JOB-2025-001)")
@click.option("--customer", "customer_id", type=int, default=None, help="All deals for a customer")
@click.option("--all-deals", is_flag=True, help="Report on all deals")
@click.option(
    "--format", "fmt",
    type=click.Choice(["terminal", "pdf", "html", "all"]),
    default="terminal",
    show_default=True,
    help="Output format",
)
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory")
def report_generate(deal_ref, customer_id, all_deals, fmt, output):
    """Generate a report for deals."""
    from dealtracker.reports.generator import generate_deal_report, generate_full_report

    if not any([deal_ref, customer_id, all_deals]):
        console.print("[red]Specify --deal, --customer, or --all-deals.[/red]")
        raise SystemExit(1)

    out = Path(output) if output else None

    with get_session() as session:
        if deal_ref:
            from dealtracker.commands.deals import _lookup_deal
            deal = _lookup_deal(session, deal_ref)
            if not deal:
                console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
                raise SystemExit(1)
            generate_deal_report(deal.id, session, fmt=fmt, output_dir=out)
        else:
            generate_full_report(
                session,
                fmt=fmt,
                output_dir=out,
                customer_id=customer_id,
            )


@report_group.command("list")
def report_list():
    """List previously generated reports."""
    from dealtracker.config import REPORTS_DIR

    reports = sorted(REPORTS_DIR.rglob("*.html")) + sorted(REPORTS_DIR.rglob("*.pdf"))
    reports = sorted(set(reports))

    if not reports:
        console.print("[dim]No reports found.[/dim]")
        return

    console.print(f"\n[bold]Reports in {REPORTS_DIR}:[/bold]")
    for r in sorted(reports):
        console.print(f"  {r.relative_to(REPORTS_DIR)}")
