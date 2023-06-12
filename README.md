# Nio-Botlib
A simple, easy to use python Matrix bot library, based on the popular 
[matrix-nio](https://pypi.org/project/matrix-nio/) library.

NBL is designed to have a similar (as similar as reasonably possible) design and feel to the popular 
[discord.py](https://pypi.org/project/discord.py) library, which should hopefully give it a familiar feel if you're
coming from a discord background.

Please note that there *will* be teething problems as matrix is very confusing, and some advanced features may not be
available, as with any client.

## Installation
```bash
pip install git+https://github.com/EEKIM10/nio-botlib
```
Or with E2EE support (you have to have libolm installed):
```bash
pip install git+https://github.com/EEKIM10/nio-botlib#egg=nio-botlib[e2ee]
```

## Features
Active early alpha: [TODO.md](/TODO.md)

## Quickstart
```python
import time
from niobot import Bot, Context

bot = Bot(
    homeserver="https://matrix.org",  # your homeserver
    user_id="@__example__:matrix.org",  # the user ID to log in as (Fully qualified)
    password="password",  # You should not use your password in production. Use an access token instead.
    command_prefix="!",  # the prefix to respond to (case sensitive, must be lowercase if below is True)
    case_insensitive=True,  # messages will be lower()cased before being handled. This is recommended.
    owner_id="@owner:homeserver.com"  # The user ID who owns this bot. Optional, but required for bot.is_owner(...).
)

@bot.register()  # tells the bot to register a command
async def ping(ctx: Context):  # Commands can only have one argument, which is the context.
    """Shows the latency"""  # a description to be shown in <prefix>help (optional)
    roundtrip = (time.time() * 1000 - ctx.event.server_timestamp)
    # time.time() * 1000 gets the current timestamp in milliseconds, since server_timestamp is in milliseconds
    # Subtracting the server timestamp from our current timestamp shows how long it took for us to get the server event
    await ctx.reply("Pong! Took {:,.2f}ms".format(roundtrip))
    # ctx.reply() sends a message to the room the command was invoked in, and automatically adds a reply marker
    # This is recommended when responding to a command, as it makes it easier to follow the conversation, and can
    # prevent spam by having ownership over commands.

@bot.register(name="echo", disabled=True)  # creates !echo, but disables the command (it won't show up in help, or run)
def do_echo(ctx: Context):
    """Repeats what you say!"""
    await ctx.reply(f"You said: {' '.join(ctx.arguments)}")

bot.run()  # starts the bot
```