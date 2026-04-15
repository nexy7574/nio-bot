# Nio-Bot is deprecated

NioBot has been an amazing project and a sturdy SDK for several years now. However, several complications have meant
that, as time has marched forward, NioBot has increasingly been left in the past, slowly rotting away, even with
maintenance. Furthermore, I no longer even use the library myself, and hardly write Python code anymore, so it makes
little sense for me to continue maintaining it.

Thank you to everyone who has contributed to the project, whether that be through code, documentation, or just by using
it and giving feedback.

**If you need an alternative library**, I strongly recommend [maubot](https://mau.bot), or the underlying library it
uses, [mautrix-python](https://docs.mau.fi/python/latest/). Both of these are exceptionally high quality libraries, and
you may find them even easier to use.

The domain `nio-bot.dev` will not be renewed after this notice is posted, so the hosted documentation will eventually go
offline. The GitHub repository will remain online, but it will be archived and set to read-only.

<details>
<summary>pre-archive README</summary>

# Nio-Bot

## Making Matrix bots simple

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

* End-to-End encryption support: `nio-bot[e2ee]`
* The CLI (recommended): `nio-bot[cli]`
* Both: `nio-bot[cli,e2ee]`
* Development dependencies: `nio-bot[dev]`

Please note that `e2ee` uses `olm`, which depends on `libolm`. You can likely install this though
your system package manager.
To install the `dev` extra (for developing niobot itself), you will additionally need
cmake, gcc, g++, python devel, and rustc.

## Features

Nio-Bot extends [matrix-nio](https://pypi.org/project/matrix-nio), sitting on top of it, and simply
providing a unified command interface, honing the base client to be more suited to bots and other
automated applications.

Nio-Bot comes with a whole host of features to help make your development experience as easy as
possible. Some features include, but are not limited to:

* A powerful commands framework (Modules, aliases, checks, easy extensibility)
* Custom argument parser support
* A flexible event system
* Simple end-to-end encryption
* Automatic markdown rendering when sending/editing messages
* Super simple to use Attachments system
* Very customisable monolithic client instance
* A simple, easy-to-use CLI tool for some on-the-go tasks
* Full attachment support (File, Image, Audio, Video), with encryption support
* [In-depth, simple, clean documentation](https://docs.nio-bot.dev/stable)

## Help

You can join our [Matrix Room](https://matrix.to/#/#niobot:nexy7574.co.uk) for help, or to just chat.
You can also get the latest updates in development there, including having your say in how new
things are implemented!

## A quick example

```python
# This example was written using version 1.1.0.
import niobot

client = niobot.NioBot(
    # Note that all of these options other than the following are optional:
    # * homeserver
    # * user_id
    # * command_prefix
    homeserver="https://matrix.example.org",  # it is important that you use the matrix server, not the delegation URL
    user_id="@example1:example.org",
    device_id="my-device-name",
    command_prefix="!",
    case_insensitive=True,
    owner_id="@example2:example.org",
    ignore_self=True  # default is True, set to false to not ignore the bot's own messages
)

@client.on_event("ready")
async def on_ready(sync_result: niobot.SyncResponse):
    print("Logged in!")


# A simple command
@client.command()
async def ping(ctx: niobot.Context):
    latency = ctx.latency
    await ctx.respond(f"Pong! {latency:.2f}ms")


# A command with arguments
@client.command()
async def echo(ctx: niobot.Context, *, message: str):
    await ctx.respond("You said: " + message)


client.run(access_token="...")
```

### Using the CLI to get an access token

If you install the cli extras, you can use `niocli` to get an access token
from a username and password (read [this](https://docs.nio-bot.dev/stable/guides/001-getting-started/#why-is-logging-in-with-a-password-so-bad) for why you'd want to use an access token):

```bash
niocli get-access-token -U '@example1:example.org' -D 'my-device-name'
```

After putting in your password, an access token will be printed to the console once the login is
successful.

## Further reading

Look at the [docs](https://docs.nio-bot.dev) for more information on how to use Nio-Bot, or the
[examples on GitHub](https://github.com/nexy7574/niobot).

</details>
