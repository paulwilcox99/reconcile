import click
from dealtracker.database import init_db


@click.group()
@click.version_option("0.1.0", prog_name="dt")
def cli():
    """DealTracker — track and reconcile business deals.

    \b
    Typical workflow:
      dt doc add invoice.pdf          # ingest a document
      dt deal list                    # see all deals
      dt reconcile check 1            # check deal #1
      dt report generate --deal 1     # generate report
    """
    init_db()


from dealtracker.commands.customers import customer_group
from dealtracker.commands.deals import deal_group
from dealtracker.commands.docs import doc_group
from dealtracker.commands.reconcile_cmd import reconcile_group
from dealtracker.commands.report_cmd import report_group

cli.add_command(customer_group)
cli.add_command(deal_group)
cli.add_command(doc_group)
cli.add_command(reconcile_group)
cli.add_command(report_group)


if __name__ == "__main__":
    cli()
