# NioBot
A simple, easy to use python Matrix bot library, based on the excellent
[matrix-nio](https://pypi.org/project/matrix-nio/) library.

NioBot is designed to have a similar (as similar as reasonably possible) design and feel to the
[discord.py](https://pypi.org/project/discord.py) library, which should hopefully give it a familiar feel if you're
coming from a discord background.

Please note that there *will* be teething problems, and as such some advanced features may not be
available, as with any client.

## Need help?
Take a look at the [docs!](https://nexy7574.github.io/niobot), or
[![Chat on Matrix](https://matrix.to/img/matrix-badge.svg)](https://matrix.to/#/#niobot:nexy7574.co.uk)
(dedicated support room)

---

Alternatively, take a look at my [dev bot](https://github.com/nexy7574/niobot-test), which is a bot that I use to test
features of nio-bot before they're released.
This bot is very advanced as, since I developed the library, I know exactly how it works, and will have bleeding-edge
features built into it, which a lot of users may not use yet.

It is, however, a great example of how an advanced, full feature bot can be created using this library.

You can see it live [here](https://matrix.to/#/@jimmy-bot:nexy7574.co.uk)
(DM it, the prefix is ?, and full end-to-end encryption is supported(*). Average response time is ~300-500ms)

(\* May not always work due to key store issues, but it should work most of the time, especially if its your first
time using it.)

## Installation
### Release versions
You can use the [PyPi](https://pypi.org/project/nio-bot) releases:
```python
nio-bot==1.0.0  # or whatever version
# Or to install it with extras
nio-bot[e2ee,cli]==1.0.0
```

### Development (master branch)
You should use requirements.txt:
```python
nio-bot @ git+https://github.com/nexy7574/niobot.git
# Or with e2ee support (note you will need libolm)
nio-bot[e2ee] @ git+https://github.com/nexy7574/niobot.git
```
You can figure out how to install it in other ways.

## Features
NioBot aims to be as easy to use as possible, so form is preferred over function.
Some features you'd normally expect may not be implemented (yet, feel free to open a pull request!) or may not work as
intended or how you'd expect, however as with any matrix client.

## Quickstart
```python
import time
from niobot import Bot, Context

bot = Bot(
    homeserver="https://matrix.org",  # your homeserver
    user_id="@__example__:matrix.org",  # the user ID to log in as (Fully qualified)
    command_prefix="!",  # the prefix to respond to (case sensitive, must be lowercase if below is True)
    case_insensitive=True,  # messages will be casefold()ed before being handled. This is recommended.
    owner_id="@owner:homeserver.com"  # The user ID who owns this bot. Optional, but required for bot.is_owner(...).
)

@bot.command()  # tells the bot to register a command
async def ping(ctx: Context):  # Commands can only have one argument, which is the context.
    """Shows the latency"""  # a description to be shown in <prefix>help (optional)
    roundtrip = (time.time() * 1000 - ctx.event.server_timestamp)
    # time.time() * 1000 gets the current timestamp in milliseconds, since server_timestamp is in milliseconds
    # Subtracting the server timestamp from our current timestamp shows how long it took for us to get the server event
    await ctx.reply("Pong! Took {:,.2f}ms".format(roundtrip))
    # ctx.reply() sends a message to the room the command was invoked in, and automatically adds a reply marker
    # This is recommended when responding to a command, as it makes it easier to follow the conversation, and can
    # prevent spam by having ownership over commands.

@bot.command(name="echo", disabled=True)  # creates !echo, but disables the command (it won't show up in help, or run)
def do_echo(ctx: Context):
    """Repeats what you say!"""
    # DO NOT USE THIS COMMAND IN YOUR CODE, IF YOUR BOT HAS @ROOM PERMISSIONS
    # AND SOMEONE SAYS '!ECHO @ROOM', THE BOT WILL JUST GLEEFULLY ECHO BACK '@ROOM'!
    await ctx.reply(f"You said: {' '.join(ctx.arguments)}")

bot.run(password="password")  # starts the bot with a password. If you already have a login token, see:
bot.run(access_token="my_token") # starts the bot with a login token.
```

### With modules
Eventually, you will want to split your code up into several "modules" to make your code easier to read, and also
modular. You can do this using the `NioBot.mount_module` function.

> Note: Once a module is loaded, you cannot "reload" it. You can unload it, but there is no way to refresh code yet.

Let's assume this file tree:
```
project_root
|- main.py  (your bot file, the bit that runs your bot)
|- modules
    |- ping.py
```

In main.py, you'll put some similar code:
```python
import niobot

bot = niobot.Bot(...)
bot.mount_module("modules.ping")  # mounts the ping module

bot.run(password="password")
```

When you call `mount_module`, it effectively calls `import module` under the hood, and then does one of the following:

1. Calls the `module.setup(bot)` function, if it exists
2. Discovers all classes that subclass `niobot.Module` in the module, and calls their `__setup__`, adding all commands
registered under that class

Take the following file as ping.py:
```python
import niobot


class MyPingModule(niobot.Module):
    # This class is a subclass of niobot.Module, so it will be automatically discovered and loaded
    # It also has two attributes defined that you can use:
    # * self.bot: the instance of the bot
    # * self.log: An instance of logging.Logger, which you can use to log messages to the console or log file.
    #   It is recommended to use this instead of print().

    # Now we will define a command
    @niobot.command()
    async def ping(self, ctx: niobot.Context):
        """Shows the latency"""
        roundtrip = ctx.bot.latency(ctx.message)
        await ctx.reply("Pong! Took {:,.2f}ms".format(roundtrip))
```

Notice how here, we use `@niobot.command`, instead of `@bot.command`? They work the same, however
`niobot.command` is designed to be loaded in a module context, where you usually don't have the bot instance at runtime
(since that is injected by `NioBot.mount_module`). If you do have the bot instance, you can use `@bot.command` instead,
which will register your command instantly.

Once `mount_module` is called, it will scan through `ping.py`. It will find `MyPingModule`, realise it is a subclass
of `Module`, and will automatically add any commands defined by `@niobot.command`.

After all of this, `[prefix]ping` is now available!

---

You can customise the behaviour of the loading process at two-levels:

1. By overriding `Module.__setup__`, you can customise how the module is loaded. By default, it will scan through the
class' functions and detect any that're annotated with `@niobot.command`, and register them. You can override this
to do whatever you want.
2. Providing a `setup(niobot)` function in your module. This will be called when the module is loaded, and you can
do whatever you want in here. This is useful if you want to do something that isn't related to commands, such as
registering event handlers. Note that defining `setup` must be outside any classes, and it will disable the
auto-discovery of commands.
