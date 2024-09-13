"""
This example shows you several ways to use command arguments in NioBot.

Basic setup (getting credentials) will not be covered in this example.
"""
from ipaddress import IPv4Address, IPv4Network
from typing import Annotated, Union

import aiohttp
from custom_converters import IPConverter

import niobot

with open("./token.txt") as fd:
    TOKEN = fd.read().strip()


bot = niobot.NioBot(
    "https://matrix.example",
    "@user:matrix.example",
    command_prefix="!"
)


@bot.command("http.get")
async def get_url(
    ctx: niobot.Context,  # Context is never an argument the user can supply.
    url: str  # this is a required argument that will always be a string
):
    """
    This command will fetch the content of the given URL and return it.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            status = response.status
            content = await response.read()

    return await ctx.respond(f"Status: {status}\nContent: {len(content):,} bytes")


@bot.command("length")
async def length(
    ctx: niobot.Context,
    text: str = None  # this argument is a string, but if not supplied, it will be None.
    # This could also be:
    # text: str | None = None  (python >=3.10)
    # or
    # text: typing.Optional[str] = None  (python 3.9)
):
    """
    This command will return the length of the given text.
    """
    return await ctx.respond(f"Length: {len(text)}")


@bot.command("ip-exists")
async def ip_exists(
    ctx: niobot.Context,
    ip: Annotated[Union[IPv4Address, IPv4Network], IPConverter]
    # `Annotated` allows you to use custom parsers for arguments.
    # The first value of the annotation is the real type, the second is the parser.
    # You *could* just use `ip: IPConverter` but this is better for type-hinting.
):
    """
    This command will return whether the given IP address or network exists.
    """
    await ctx.respond(f"IP: {ip}")
    if isinstance(ip, IPv4Network):
        return await ctx.respond(f"This network has {len(ip.hosts())} possible hosts.")


bot.run(TOKEN)
