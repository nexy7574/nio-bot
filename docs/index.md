# Index

Welcome to the Nio-Bot Documentation

## What is NioBot?

NioBot (& nio-bot) is a framework built upon the [matrix-nio](https://pypi.org/p/matrix-nio) client library, built with the creation of bots in mind.
NioBot provides a simple and intuitive way to build bots for the Matrix framework by simplifying a lot of the mundane tasks that come with building a bot.

By making use of `nio`, you can access the full power of the Matrix protocol, while still being able to build a bot using `nio-bot` with ease.

??? info "Why NioBot, and not just regular nio?"
    Take for example, the following code:

    ```python
    from niobot import NioBot, Context


    bot = NioBot(
        homeserver="https://matrix-client.matrix.org",
        user_id="@my_user:matrix.org",
        command_prefix="!"
    )

    @bot.command("ping")
    async def ping_command(ctx: Context):
        """Checks if the bot is online & responding."""
        await ctx.respond("Pong!")


    bot.run(access_token="abc123")
    ```

    This is an incredibly simple working example of a bot that responds to the command `!ping` with `Pong!`. You simply run this with `python3 bot.py`, and you're away!

    Here's the same code (not fully, there are a LOT of behind the scenes in niobot) in base `nio`:

    ```python
    import asyncio
    from nio import AsyncClient, MatrixRoom, RoomMessage


    client = AsyncClient("https://matrix-client.matrix.org", "@my_user:matrix.org")


    async def ping_command(room: MatrixRoom, event: RoomMessage):
        if event.sender == client.user_id:
            return
        body = event.body
        if event.body.startswith("!"):
            if event.body.split()[0][1:].lower() == "ping":
                await client.room_send(
                    room.room_id,
                    "m.room.message",
                    {
                        "msgtype": "m.notice",
                        "body": "Pong!",
                        "m.relates_to": {
                            "m.in_reply_to": {
                                "event_id": event.event_id
                            }
                        }
                    }
                )


    client.add_event_callback(ping_command, (RoomMessage,))
    client.access_token = "abc123"

    asyncio.run(client.sync_forever())
    ```

    At first, it doesn't look too difficult right? But, as you start to add more commands, or add more functionality, you'll end up building up more and more boilerplate,
    and it can get quite messy quite quickly.

    This is where `nio-bot` comes in. By abstracting away a lot of the nuanced functionality in favour of a simplified interface, so that you can focus on building meaningful code,
    rather than annoying boilerplate.

## Features

NioBot contains [all of the features of matrix-nio](https://matrix-nio.readthedocs.io/en/latest/index.html#features), plus a few more:

- **Integrated command system**: Easily create commands with a decorater and function. That's all you need.
- **Powerful context**: Access all of the metadata you need about a command with the `[niobot.Context][]` object, given to every command.
- **Robust error handling**: Your bot won't crash as soon as an error occurs. Instead, it will be passed on to a handler, and the bot will continue running.
- **Simple configuration**: Pass in a few parameters to `[niobot.NioBot][]`, and you're ready to go.
- **Automatic Markdown + HTML rendering**: Send messages in markdown or HTML, and NioBot will automatically render them for you.
- **Easy events**: Listening for events in NioBot is incredibly similar to listening for commands, and is just as easy.


??? danger "NioBot does not make an effort to support end-to-end encryption"
    While NioBot does support end-to-end encryption, it does not make an effort to support it.
    Making end-to-end encryption work in a headless fashion is incredibly difficult, and while it does work, users have reported that E2EE is
    unreliable and can unexpectedly break at any time, and is hard to debug.

    We do not recommend that you expect E2EE to work when building a bot with NioBot. If it works, that's great! If not, **we cannot help**.

## Installation

You can install NioBot from PyPi:

```bash
pip install nio-bot
# Or, get the latest pre-release
pip install --pre nio-bot
```

or straight from git:

```bash
pip install git+https://github.com/nexy7574/nio-bot.git
```

## Contact

See the [Matrix room](https://matrix.to/#/#niobot:nexy7574.co.uk) for help, or open a [GitHub issue](https://github.com/nexy7574/nio-bot/issues/new) for bugs or feature requests.
