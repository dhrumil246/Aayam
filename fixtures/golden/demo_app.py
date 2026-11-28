import click


@click.command()
@click.option("--json", "fmt", flag_value="json", conflicts_with=["--yaml"], help="Output JSON.")
@click.option("--yaml", "fmt", flag_value="yaml", conflicts_with=["--json"], help="Output YAML.")
@click.option("--verbose", is_flag=True, help="Verbose output.")
def cli(fmt, verbose):
    click.echo(f"fmt={fmt} verbose={verbose}")
