# Nio-Botlib
A simple, easy to use python Matrix bot library, based on the popular 
[matrix-nio](https://pypi.org/project/matrix-nio/) library.

NBL is designed to have a similar (as similar as reasonably possible) design and feel to the popular 
[discord.py](https://pypi.org/project/discord.py) library, which should hopefully give it a familiar feel if you're
coming from a discord background.

Please note that there *will* be teething problems as matrix is very confusing, and some advanced features may not be
available, as with any client.

## Need help?
look at [examples](/examples), open an issue, or [contact me on matrix](https://matrix.to/#/@nex:nexy7574.co.uk)

## Examples
You can see the [examples](/examples) directory, which contains a few examples of how to use Nio-Botlib.
Note that these examples are not tested and will need some tweaking.

---

Alternatively, take a look at my [dev bot](https://github.com/EEKIM10/niobot-test), which is a bot that I use to test
features of nio-bot before they're released.
This bot is very advanced as, since I developed the library, I know exactly how it works, and will have bleeding-edge
features built into it, which a lot of users may not use yet.

It is, however, a great example of how an advanced, full feature bot can be created using this library.

## Installation
```bash
pip install git+https://github.com/EEKIM10/nio-botlib
```
Or with E2EE support (you have to have libolm installed):
```bash
pip install git+https://github.com/EEKIM10/nio-botlib#egg=nio-botlib[e2ee]
```

## Features
Nio-bot aims to be as easy to use as possible, so form is preferred over function. This means that some features may be
missing, such as full E2EE (it *is* supported, however is very hit or miss), and other newer features.

However, like any good client, NB tries to adhere to the 
[Matrix Spec](https://spec.matrix.org/v1.7/client-server-api) (in terms of design at least, all the hard work is 
done by matrix-nio)

## Quickstart
```python
import time
from niobot import Bot, Context

bot = Bot(
    homeserver="https://matrix.org",  # your homeserver
    user_id="@__example__:matrix.org",  # the user ID to log in as (Fully qualified)
    command_prefix="!",  # the prefix to respond to (case sensitive, must be lowercase if below is True)
    case_insensitive=True,  # messages will be lower()cased before being handled. This is recommended.
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
import niolib

bot = niolib.Bot(...)
bot.mount_module("modules.ping")  # mounts the ping module

bot.run(password="password")
```

When you call `mount_module`, it effectively calls `import module` under the hood, and then does one of the following:

1. Calls the `module.setup(bot)` function, if it exists
2. Discovers all classes that subclass `niolib.Module` in the module, and calls their `__setup__`, adding all commands
registered under that class

Take the following file as ping.py:
```python
import niolib


class MyPingModule(niolib.Module):
    # This class is a subclass of niolib.Module, so it will be automatically discovered and loaded
    # It also has two attributes defined that you can use:
    # * self.bot: the instance of the bot
    # * self.log: An instance of logging.Logger, which you can use to log messages to the console or log file.
    #   It is recommended to use this instead of print().
    
    # Now we will define a command
    @niolib.command()
    async def ping(self, ctx: niolib.Context):
        """Shows the latency"""
        roundtrip = (time.time() * 1000 - ctx.event.server_timestamp)
        await ctx.reply("Pong! Took {:,.2f}ms".format(roundtrip))
```

Notice how here, we use `@niolib.command`, instead of `@bot.command`? They work the same, however
`niolib.command` is designed to be loaded in a module context, where you usually don't have the bot instance at runtime
(since that is injected by `NioBot.mount_module`). If you do have the bot instance, you can use `@bot.command` instead,
which will register your command instantly.

Once `mount_module` is called, it will scan through `ping.py`. It will find `MyPingModule`, realise it is a subclass
of `Module`, and will automatically add any commands defined by `@niolib.command`.

After all of this, `[prefix]ping` is now available!

---

You can customise the behaviour of the loading process at two-levels:

1. By overriding `Module.__setup__`, you can customise how the module is loaded. By default, it will scan through the
class' functions and detect any that're annotated with `@niolib.command`, and register them. You can override this
to do whatever you want.
2. Providing a `setup(niobot)` function in your module. This will be called when the module is loaded, and you can
do whatever you want in here. This is useful if you want to do something that isn't related to commands, such as
registering event handlers. Note that defining `setup` must be outside any classes, and it will disable the
auto-discovery of commands.