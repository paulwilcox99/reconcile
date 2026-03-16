import click
from rich.console import Console
from dealtracker.database import get_session
from dealtracker.models import Customer
from dealtracker.reports.terminal_report import print_customers_table
from dealtracker.utils import make_slug

console = Console()


@click.group("customer")
def customer_group():
    """Manage customers."""


@customer_group.command("list")
def customer_list():
    """List all customers."""
    with get_session() as session:
        customers = session.query(Customer).order_by(Customer.name).all()
        print_customers_table(customers)


@customer_group.command("show")
@click.argument("customer_id", type=int)
def customer_show(customer_id):
    """Show a customer and all their deals."""
    from dealtracker.reports.terminal_report import print_deals_table
    with get_session() as session:
        c = session.get(Customer, customer_id)
        if not c:
            console.print(f"[red]Customer {customer_id} not found.[/red]")
            raise SystemExit(1)
        console.print(f"\n[bold]Customer:[/bold] {c.name}  (ID: {c.id})")
        if c.email:
            console.print(f"[bold]Email:[/bold] {c.email}")
        if c.phone:
            console.print(f"[bold]Phone:[/bold] {c.phone}")
        if c.notes:
            console.print(f"[bold]Notes:[/bold] {c.notes}")
        console.print()
        print_deals_table(c.deals)


@customer_group.command("add")
@click.option("--name", "-n", required=True, prompt=True, help="Customer name")
@click.option("--email", "-e", default=None, help="Customer email")
@click.option("--phone", "-p", default=None, help="Customer phone")
@click.option("--notes", default=None, help="Notes")
def customer_add(name, email, phone, notes):
    """Add a customer manually."""
    with get_session() as session:
        slug = make_slug(name)
        existing = session.query(Customer).filter_by(slug=slug).first()
        if existing:
            console.print(f"[yellow]Customer already exists:[/yellow] {existing.name} (ID: {existing.id})")
            return
        c = Customer(name=name, slug=slug, email=email, phone=phone, notes=notes)
        session.add(c)
        session.flush()
        console.print(f"[green]Customer added:[/green] {c.name} (ID: {c.id})")
