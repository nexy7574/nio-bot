# Nio-Bot

## Making Matrix bots simple

![GitHub Workflow Status (with event)](https://img.shields.io/github/actions/workflow/status/nexy7574/niobot/python-package.yml?style=flat-square&logo=github&label=Package)
[![GitHub issues](https://img.shields.io/github/issues/nexy7574/niobot?style=flat-square&logo=github)](https://github.com/nexy7574/niobot/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/nexy7574/niobot?style=flat-square&logo=github)](https://github.com/nexy7574/niobot/pulls)
![GitHub](https://img.shields.io/github/license/nexy7574/niobot?style=flat-square&logo=github)
[![GitHub Repo stars](https://img.shields.io/github/stars/nexy7574/niobot?style=flat-square&logo=github&label=stars%20%E2%AD%90&color=gold)](https://github.com/nexy7574/niobot/stargazers)

[![PyPI - Downloads](https://img.shields.io/pypi/dm/nio-bot?style=flat-square&logo=pypi)](https://pypi.org/project/nio-bot)
[![PyPI - Version](https://img.shields.io/pypi/v/nio-bot?style=flat-square&logo=pypi)](https://pypi.org/project/nio-bot)
[![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fnexy7574%2Fniobot%2Fmaster%2Fpyproject.toml&style=flat-square&logo=python)](https://pypi.org/project/nio-bot)

[![Matrix](https://img.shields.io/matrix/niobot%3Anexy7574.co.uk?server_fqdn=matrix.org&style=flat-square&logo=matrix&link=https%3A%2F%2Fmatrix.to%2F%23%2F%23niobot%3Anexy7574.co.uk)](https://matrix.to/#/#niobot:nexy7574.co.uk)

---

## Installing

You can install the latest stable release from PyPi:

```bash
pip install nio-bot
# Or for cutting-edge releases:
# pip install --pre nio-bot
```

You may also want some extras:

* End to End encryption support: `nio-bot[e2ee]`
* The CLI (recommended): `nio-bot[cli]`
* Both: `nio-bot[cli,e2ee]`
* Development dependencies: `nio-bot[dev]`

Please note that `e2ee` uses `olm`, which depends on `libolm`. You can likely install this though your system package manager.

## Features

Nio-Bot is built on the solid client library, [matrix-nio](https://pypi.org/project/matrix-nio). This means that you get the full experience of a 
Matrix client, with the added benefit of being able to easily create bots.

Nio-Bot comes with a whole host of features to help make your development experience as easy as possible.
Some features include, but are not limited to:

* A powerful commands framework (Modules, aliases, checks, easy extensibility)
* Custom argument parser support
* A flexible event system
* Simple end-to-end encryption
* Automatic markdown rendering when sending/editing messages
* Super simple to use Attachments system
* Very customisable monolithic client instance
* A simple, easy-to-use CLI tool for some on-the-go tasks
* Full attachment support (File, Image, Audio, Video), with encryption support
* [In-depth, simple, clean documentation](https://docs.nio-bot.dev)

## Help

You can join our [Matrix Room](https://nio-bot.dev/support) for help, or to just chat.
You can also get the latest updates in development there, including having your say in how new things are implemented!

## A quick example

```python
# This example was written using version 1.1.0.
import niobot

client = niobot.NioBot(
    # Note that all of these options other than the following are optional:
    # * homeserver
    # * user_id
    # * command_prefix
    homeserver="https://matrix.example.org",
    user_id="@example1:example.org",
    device_id="my-device-name",
    command_prefix="!",
    case_insensitive=True,
    owner_id="@example2:example.org",
    ignore_self=False
)

@client.on_event("ready")
async def on_ready(sync_result: niobot.SyncResponse):
    print("Logged in!")


# A simple command
@client.command()
async def ping(ctx: niobot.Context):
    latency = ctx.latency
    await ctx.reply("Pong!")


# A command with arguments
@client.command()
async def echo(ctx: niobot.Context, *, message: str):
    await ctx.respond(message)


client.run(access_token="aaaaaaaaaaaaaa")
```

### Using the CLI to get an access token

If you install the cli extras, you can use `niocli` to get an access token
from a username and password (read [this](https://docs.nio-bot.dev/guides/001-getting-started/#why-is-logging-in-with-a-password-so-bad) for why you'd want to use an access token):

```bash
niocli get-access-token -u '@example1:example.org' -d 'my-device-name'
```

After putting in your password, an access token will be printed to the console once the login is successful.

## Further reading

Look at the [docs](https://docs.nio-bot.dev) for more information on how to use Nio-Bot, or the [examples on github](https://github.com/nexy7574/niobot).
