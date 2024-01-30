import asyncio
import importlib.metadata
import logging
import os
import pathlib
import re
import shutil
import sys
import typing

import packaging.specifiers
import packaging.version

import niobot

try:
    import click
    import httpx
    import psutil
except ImportError:
    print("Missing CLI dependencies. Did you install CLI extras?", file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger("niobot.cli")


def versions(package_name: str) -> typing.List[packaging.version.Version]:
    response = httpx.get(
        "https://pypi.org/simple/%s/" % package_name,
        headers={
            "User-Agent": "nio-bot (CLI, https://github.com/nexy7574/niobot)",
            "Accept": "application/vnd.pypi.simple.v1+json",
        },
    )
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/vnd.pypi.simple.v1+json"
    return list(map(packaging.version.parse, response.json()["versions"]))


@typing.overload
def get_installed_version(package_name: str, default_to_0_0_0: bool = True, *, parse: typing.Literal[False]) -> str: ...


@typing.overload
def get_installed_version(
    package_name: str, default_to_0_0_0: bool = True, *, parse: typing.Literal[True]
) -> packaging.version.Version: ...


def get_installed_version(
    package_name: str, default_to_0_0_0: bool = True, *, parse: bool = False
) -> typing.Union[str, packaging.version.Version]:
    """
    Fetches a package version via importlib.metadata.

    :param package_name: The name of the package to fetch.
    :param default_to_0_0_0: Whether to default to "0.0.0" if the package is not installed or not found.
    :return: The package version identifier or packaging version
    """
    try:
        version = importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        if default_to_0_0_0:
            version = "0.0.0"
        raise

    if parse:
        version = packaging.version.parse(version)
    return version


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


@cli_root.command()
@click.option("--no-colour", "--no-color", "-C", is_flag=True, default=False)
def version(no_colour: bool):
    """Shows version information."""
    logger.info("Gathering version info...")
    import platform

    from nio.crypto import ENCRYPTION_ENABLED

    try:
        nio_version = get_installed_version("matrix-nio", parse=True)
    except (importlib.metadata.PackageNotFoundError, packaging.version.InvalidVersion) as e:
        logger.critical("Failed to resolve matrix-nio version information", exc_info=e)
        nio_version = packaging.version.Version("0.0.0")

    try:
        niobot_version = get_installed_version("nio-bot", parse=True)

        # Check for updates
        niobot_versions = versions("nio-bot")
        newest = tuple(filter(lambda v: v.pre is None and v.dev is None, niobot_versions))[-1]
        if newest > niobot_version:
            logging.warning("There is an update to nio-bot available: %s", niobot_version)
    except (importlib.metadata.PackageNotFoundError, packaging.version.InvalidVersion) as e:
        logger.critical("Failed to resolve nio-bot version information", exc_info=e)
        niobot_version = packaging.version.Version("0.0.0")

    is_release_version = not any(
        (niobot_version.is_devrelease, niobot_version.is_prerelease, niobot_version.is_postrelease)
    )
    niobot_version_pretty = niobot_version.public
    if not is_release_version:
        build = niobot_version.base_version
        dev_build = niobot_version.dev or "N/A"
        post = niobot_version.post or "N/A"
        pre = "".join(map(str, niobot_version.pre or ("N/A",)))
        commit = niobot_version.local or "N/A"

        niobot_version_pretty += f" (v{build}, build {dev_build}, pre {pre}, post {post}, commit {commit})"

    _os = platform.platform()
    if sys.version_info > (3, 9):
        if hasattr(platform, "freedesktop_os_release"):
            try:
                _os_info = platform.freedesktop_os_release()
            except OSError:
                pass
            else:
                _os += " ({0}/{1} - {2})".format(
                    _os_info.get("NAME", "Unknown"),
                    _os_info.get("VERSION", "Unknown"),
                    _os_info.get("PRETTY_NAME", "Unknown"),
                )

    space = {"total": 0}
    for mount in psutil.disk_partitions():
        try:
            usage = shutil.disk_usage(mount.mountpoint)
            free_percent = (usage.free / usage.total) * 100
            space["total"] += usage.free
            space[mount.mountpoint] = round(free_percent, 2)
        except PermissionError:
            pass
    space_total = space.pop("total")

    supported_python_versions_raw = importlib.metadata.metadata("nio-bot")["Requires-Python"]
    supported_python_versions = packaging.specifiers.SpecifierSet(supported_python_versions_raw)
    if not supported_python_versions.contains(platform.python_version()):
        python_version_supported = False
    else:
        python_version_supported = True

    nio_versions_raw = ""
    for version in importlib.metadata.requires("nio-bot"):
        if version.startswith("matrix-nio"):
            nio_versions_raw = version.split(" ")[1]
            break
    nio_versions = packaging.specifiers.SpecifierSet(nio_versions_raw)
    if not nio_versions.contains(nio_version):
        nio_version_supported = False
    else:
        nio_version_supported = True

    lines = [
        ["NioBot version", niobot_version_pretty, lambda x: True],
        ["matrix-nio version", nio_version, lambda x: nio_version_supported],
        ["Python version", platform.python_version(), lambda x: python_version_supported],
        ["Python implementation", platform.python_implementation(), lambda x: x == "CPython"],
        ["Operating System", _os, lambda val: val.startswith(("Windows", "Linux"))],
        ["Architecture", platform.machine(), lambda x: x == "x86_64"],
        ["OLM Installed", "Yes" if ENCRYPTION_ENABLED else "No", lambda x: x != "No"],
        ["Free Disk Space", " ".join(f"{k} ({v}%)" for k, v in space.items()), lambda x: space_total > 1024**3],
    ]

    _docker_path = pathlib.Path("/.dockerenv")
    if _docker_path.is_file():
        lines.append(["Running in Docker", "Probably (/.dockerenv exists)", lambda _: True])

    click.echo()
    for line in lines:
        if no_colour:
            click.echo("%s: %s" % tuple(line)[:2])
        else:
            click.echo(
                click.style(line[0], fg="cyan") + ": " + click.style(line[1], fg="green" if line[2](line[1]) else "red")
            )
    click.echo()


@cli_root.command(name="test-homeserver")
@click.argument("homeserver")
def test_homeserver(homeserver: str):
    """Walks through resolving and testing a given homeserver."""
    import urllib.parse

    import httpx

    if homeserver.startswith("@"):
        _, homeserver = homeserver.split(":", 1)

    logger.debug("Parsing given input %r as a URL...", homeserver)
    parsed = urllib.parse.urlparse(homeserver)
    if not parsed.scheme:
        logger.debug("No scheme found, assuming HTTPS.")
        parsed = urllib.parse.urlparse(f"https://{homeserver}")

    if not parsed.netloc:
        logger.critical("No netloc found, cannot continue.")
        logger.critical("URI parsed to: %r", parsed)
        return

    logger.debug("Attempting to resolve %r...", parsed.netloc)
    logger.info("Trying well-known of %r...", parsed.netloc)
    base_url = None
    try:
        response = httpx.get(f"https://{parsed.netloc}/.well-known/matrix/client", timeout=30, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.critical("Failed to get well-known: %r", e)
        return
    else:
        logger.debug("Got response: %r", response)
        cors = response.headers.get("Access-Control-Allow-Origin", None)
        if not cors:
            logger.warning("No CORS header found. This homeserver will be unusable in web-based clients!")
        elif cors != "*":
            logger.warning(
                "CORS header found, but not set to wildcard. "
                "This homeserver will be unusable in most web-based clients!"
            )

        if response.status_code != 404:
            if response.status_code != 200 or len(response.content or b"") == 0:
                logger.critical("Well-known returned non-404, but no content. Failing.")
                return
            else:
                data = response.json()
                logger.debug("Well-known data: %r", data)
                if "m.homeserver" not in data:
                    logger.critical("Well-known data does not contain m.homeserver. Failing.")
                    return
                base_url = urllib.parse.urlparse(data["m.homeserver"]["base_url"])
                logger.debug("Parsed base URL: %r", base_url)
                if not base_url.scheme or not base_url.netloc:
                    logger.critical("Base URL does not contain a scheme. Invalid URL? Failing.")
                    return

    if not base_url:
        logger.info("No well-known found. Assuming %r as homeserver.", parsed.netloc)
        base_url = urllib.parse.urlparse(f"https://{parsed.netloc}")

    base_url = base_url.geturl()
    logger.info("Using %r as homeserver.", base_url)
    logger.info("Validating homeserver...")
    try:
        response = httpx.get(f"{base_url}/_matrix/client/versions", timeout=30)
    except httpx.HTTPError as e:
        logger.critical("Failed to get versions: %r", e)
        return
    else:
        data = response.json()
        logger.debug("Got response: %r", data)
        if "versions" not in data:
            logger.critical("Versions response does not contain versions. Failing.")
            return
        if "unstable_features" not in data:
            logger.warning("Versions response does not contain unstable_features. This may be bad.")

        logger.info("Homeserver validated.")
        click.secho("Homeserver validated.", fg="green")
        click.secho("%s -> %s" % (click.style(parsed.netloc, dim=True), click.style(base_url, fg="green")))


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
    "--output", "-o", "-O", default="-", help="The file to output the results to.", type=click.Path(allow_dash=True)
)
def get_access_token(path: str, username: str, password: str, homeserver: str, device_id: str):
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
        device_id = click.prompt(
            "Device ID (a memorable display name for this login, such as 'bot-production')", default=os.uname().nodename
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
            f"{homeserver}/_matrix/client/r0/login",
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
        if path != "-":
            click.secho(f'Access token: {response.json()["access_token"]}', fg="green")
            with click.open_file(path, "w+") as f:
                f.write(response.json()["access_token"])
        else:
            click.echo(response.json()["access_token"])


if __name__ == "__main__":
    cli_root()
