import click
from rich.console import Console
from dealtracker.database import get_session
from dealtracker.models import Deal, Customer
from dealtracker.reports.terminal_report import print_deals_table, print_deal_report
from dealtracker.utils import make_slug, generate_reference_number

console = Console()

STATUSES = ["open", "reconciled", "disputed", "closed", "incomplete", "all"]


@click.group("deal")
def deal_group():
    """Manage deals."""


@deal_group.command("list")
@click.option("--customer", "-c", default=None, help="Filter by customer name (partial match)")
@click.option("--status", "-s", default="all", type=click.Choice(STATUSES), help="Filter by status")
def deal_list(customer, status):
    """List deals."""
    with get_session() as session:
        query = session.query(Deal)
        if status != "all":
            query = query.filter(Deal.status == status)
        if customer:
            query = query.join(Customer).filter(Customer.name.ilike(f"%{customer}%"))
        deals = query.order_by(Deal.customer_id, Deal.id).all()
        print_deals_table(deals)


@deal_group.command("show")
@click.argument("deal_ref")
def deal_show(deal_ref):
    """Show deal detail. Accepts deal ID number or reference (e.g. 1 or JOB-2025-001)."""
    from dealtracker.reconciliation.engine import reconcile_deal
    with get_session() as session:
        deal = _lookup_deal(session, deal_ref)
        if not deal:
            console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
            raise SystemExit(1)
        result = reconcile_deal(deal.id, session)
        print_deal_report(deal, deal.documents, result)


@deal_group.command("new")
@click.option("--customer", "-c", required=True, prompt="Customer name", help="Customer name")
@click.option("--description", "-d", required=True, prompt="Job description", help="Job/project description")
@click.option("--ref", default=None, help="Custom reference number (auto-generated if omitted)")
def deal_new(customer, description, ref):
    """Create a new deal and assign it a reference number."""
    with get_session() as session:
        # Find or create customer
        cust = session.query(Customer).filter(Customer.name.ilike(customer)).first()
        if not cust:
            slug = make_slug(customer)
            cust = Customer(name=customer, slug=slug)
            session.add(cust)
            session.flush()
            console.print(f"[green]New customer:[/green] {cust.name} (ID: {cust.id})")

        reference = ref or generate_reference_number(session)
        # Check reference uniqueness
        if session.query(Deal).filter_by(reference_number=reference).first():
            console.print(f"[red]Reference '{reference}' already exists.[/red]")
            raise SystemExit(1)

        deal = Deal(
            reference_number=reference,
            customer_id=cust.id,
            description=description,
            description_slug=make_slug(description),
            status="open",
        )
        session.add(deal)
        session.flush()
        console.print(
            f"\n[bold green]Deal created:[/bold green]  "
            f"[bold cyan]{deal.reference_number}[/bold cyan]  "
            f"{deal.description}  (ID: {deal.id})"
        )


@deal_group.command("set-agreed")
@click.argument("deal_ref")
@click.argument("amount", type=float)
def deal_set_agreed(deal_ref, amount):
    """Manually set the agreed amount for a deal."""
    with get_session() as session:
        deal = _lookup_deal(session, deal_ref)
        if not deal:
            console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
            raise SystemExit(1)
        old = deal.agreed_amount
        deal.agreed_amount = amount
        console.print(
            f"[green]{deal.reference_number}[/green] agreed amount: "
            f"${old or 0:,.2f} → ${amount:,.2f}"
        )


@deal_group.command("close")
@click.argument("deal_ref")
@click.confirmation_option(prompt="Mark this deal as closed?")
def deal_close(deal_ref):
    """Mark a deal as closed."""
    with get_session() as session:
        deal = _lookup_deal(session, deal_ref)
        if not deal:
            console.print(f"[red]Deal '{deal_ref}' not found.[/red]")
            raise SystemExit(1)
        deal.status = "closed"
        console.print(f"[green]{deal.reference_number}[/green] marked as closed.")


def _lookup_deal(session, deal_ref: str):
    """Look up a deal by numeric ID or reference number string."""
    if str(deal_ref).isdigit():
        return session.get(Deal, int(deal_ref))
    return session.query(Deal).filter_by(reference_number=deal_ref.upper()).first()
