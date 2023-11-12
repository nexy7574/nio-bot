"""
A simple, interactive niobot example.

This script will ask for initial information interactively, and then writes it to a config file.
So, make sure you've got an interactive session on first run.

This example was written in nio-bot version 1.1.0b2.
"""
import getpass
from base64 import b16decode, b16encode
from configparser import ConfigParser
from pathlib import Path

import niobot

__author__ = "nexy7574 (@nex:nex7574.co.uk)"
__version__ = "1.1.0b2"


CONFIG_PATH = Path("./config.ini")
CONFIG_PATH.touch(exist_ok=True)
config = ConfigParser()
config.read(CONFIG_PATH)
if "niobot" not in config:
    homeserver = input("Homeserver URL (e.g. https://matrix.example.org): ")
    username = input("Username (e.g. @username:example.com): ")
    try:
        password = getpass.getpass("Password (CTRL+C to use token instead): ")
        token = None
    except KeyboardInterrupt:
        token = getpass.getpass("Token: ")
        password = None
    device_id = input("Device ID/Name (default: niobot-simple-example): ") or "niobot-simple-example"
    prefix = input("Bot prefix (default: !): ") or "!"
    owner_id = input("Owner ID (e.g. @example:example.com, default: None): ") or None
    config["niobot"] = {
        "homeserver": homeserver,
        "username": username,
        "device_id": device_id,
        "prefix": prefix,
        "owner_id": owner_id,
    }
    if password:
        config["niobot"]["password"] = b16encode(password.encode()).decode()
    if token:
        config["niobot"]["token"] = b16encode(token.encode()).decode()
    with CONFIG_PATH.open("w") as f:
        config.write(f)
else:
    homeserver = config["niobot"]["homeserver"]
    username = config["niobot"]["username"]
    password = config["niobot"].get("password")
    if password:
        password = b16decode(password.encode()).decode()
    token = config["niobot"].get("token")
    if token:
        token = b16decode(token.encode()).decode()
    if not any((password, token)):
        raise ValueError("Either password or token must be set in config")
    device_id = config["niobot"]["device_id"]
    prefix = config["niobot"]["prefix"]
    owner_id = config["niobot"].get("owner_id")

bot = niobot.NioBot(
    homeserver=homeserver,
    user_id=username,
    device_id=device_id,
    store_path=config["niobot"].get("store_path"),
    command_prefix=prefix,
    owner_id=owner_id,
)


@bot.on_event("ready")
async def on_ready(_):
    print(f"Logged in as {bot.user_id}")
    print(f"Prefix: {bot.command_prefix}")
    if config["niobot"].get("password"):
        print("Removing password in config in favour of access token.")
        config["niobot"].pop("password")
        config["niobot"]["token"] = bot.access_token
        with CONFIG_PATH.open("w") as file:
            config.write(file)


@bot.command("ping")
async def ping_command(ctx: niobot.Context):
    """A simple ping command"""
    latency = ctx.latency
    await ctx.respond(f"Pong! `{latency:.2f}ms` latency.")


@bot.command("wave")
async def wave_to(ctx: niobot.Context, user: niobot.MatrixUser):
    """Wave to a user"""
    await ctx.respond(f"*waves to {user.display_name}*")


bot.run(access_token=token, password=password)
