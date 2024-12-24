import asyncio
import logging
import platform
import re
import sys

import niobot

try:
    import click
    import httpx
except ImportError:
    print("Missing CLI dependencies. Did you install CLI extras?", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger("niobot.cli")


@click.group()
@click.option(
    "--log-level",
    "-L",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="WARNING",
)
@click.pass_context
def cli_root(ctx, log_level: str):
    """CLI utilities for nio-bot."""
    logging.basicConfig(
        level=getattr(logging, log_level),
    )


@cli_root.command(name="get-access-token")
@click.option("--username", "-U", default=None, help="The username part (without @)")
@click.option("--password", "-P", default=None, help="The password to use (will be prompted if not given)")
@click.option("--homeserver", "-H", default=None, help="The homeserver to use (will be prompted if not given)")
@click.option(
    "--device-id",
    "-D",
    "--session",
    "--session-id",
    default=None,
    help="The device ID to use (will be prompted if not given)",
)
@click.option(
    "--output",
    "-o",
    "-O",
    default="-",
    help="The file to output the results to.",
    type=click.Path(allow_dash=True),
)
def get_access_token(output: str, username: str, password: str, homeserver: str, device_id: str):
    """Fetches your access token from your homeserver."""
    if not username:
        username = ""

    while not re.match(r"@[\w\-.]{1,235}:[0-9A-Za-z\-_.]{3,253}", username):
        username = click.prompt("User ID (@username:homeserver.tld)")
        _, homeserver = username.split(":", 1)

    if not homeserver:
        _, homeserver = username.split(":", 1)

    if not password:
        password = click.prompt("Password (will not echo)", hide_input=True)

    if not homeserver:
        homeserver = click.prompt("Homeserver URL")

    if not device_id:
        node = platform.node()
        device_id = click.prompt(
            "Device ID (a memorable display name for this login, such as 'bot-production')",
            default=node,
        )

    click.secho("Resolving homeserver... ", fg="cyan", nl=False)
    try:
        homeserver = asyncio.run(niobot.resolve_homeserver(homeserver))
    except ConnectionError:
        click.secho("Failed!", fg="red")
    else:
        click.secho("OK", fg="green")

    click.secho("Getting access token... ", fg="cyan", nl=False)
    status_code = None
    try:
        response = httpx.post(
            f"{homeserver}/_matrix/client/v3/login",
            json={
                "type": "m.login.password",
                "identifier": {"type": "m.id.user", "user": username},
                "password": password,
                "device_id": device_id,
                "initial_device_display_name": device_id,
            },
        )
        status_code = response.status_code
        if status_code == 429:
            click.secho("Failed!", fg="red", nl=False)
            click.secho(" (Rate limited for {:.0f} seconds)".format(response.json()["retry_after_ms"] / 1000), bg="red")
            return
        response.raise_for_status()
    except httpx.HTTPError as e:
        click.secho("Failed!", fg="red", nl=False)
        click.secho(f" ({status_code or str(e)})", bg="red")
    else:
        click.secho("OK", fg="green")
        if output != "-":
            click.secho(f'Access token: {response.json()["access_token"]}', fg="green")
            with click.open_file(output, "w+") as f:
                f.write(response.json()["access_token"])
        else:
            click.echo(response.json()["access_token"])


if __name__ == "__main__":
    cli_root()
