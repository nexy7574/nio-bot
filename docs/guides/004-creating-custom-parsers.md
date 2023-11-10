# Creating custom parsers

!!! tip "New in version 1.1.0b1"
    This feature was added in version 1.1.0b1 - `pip install niobot>=1.1.0b1`

NioBot is loaded with some sane defaults for basic types. If you were to pass the following function as a command:
```python
async def my_command(ctx: Context, arg1: int, arg2: float, arg3: str):
    ...
```
NioBot would intelligently detect `ctx` as the context (and realise it's not intended to be something the user provides)
and `arg1` as an integer, `arg2` as a float, and `arg3` as a string.
Then, when my_command is run, the first argument would be converted to an integer from the message, the second as a 
float, and so on.

However, these built-in types only go so far - they're limited to a subset of python built-in types, and a couple
matrix-specific things (i.e. rooms and events and matrix.to links).

!!! question "This looks worryingly complicated"
    Pre `1.1.0b1`, parsers were far too flexible and inconsistent. The old structure only required you had a singular
    synchronous function that took three arguments: `ctx`, `arg`, and `user_input`.

    This was a problem for a couple reasons:

    1. The flexibility meant that it was difficult to get a uniform experience across all parsers.
    2. This was still not very flexible for customising the parsers, and often required wrappers.

    However, since 1.1.0b1, the parser structure now uses two new ABC classes, `Parser` and `StatelessParser`, to ensure
    that all parsers are consistent and easy to use, while still being flexible and configurable.
    As a result of using classes though, some parsers can still feel a little bit bulky. But that's okay!

## Creating a parser
Creating a parser is actually really easy. All the library needs from you is a class that subclasses either of the
parser ABCs (see below), and implements the `__call__` dunder method!

For example:
```python
from niobot.utils.parsers import StatelessParser
from niobot import CommandParserError


class UserParser(StatelessParser):
    def __call__(self, ctx: Context, arg: Argument, value: str):
        # Do some stuff here
        if "@" not in value:
            # Always raise CommandParserError when its an invalid value - this allows for proper error handling.
            raise CommandParserError("Invalid user ID. Expected @user:example.com")
        return value[1:]  # Remove the @ from the user ID
```

You can then use this parser in your commands like so:
```python
import niobot
import typing
from my_parsers import UserParser


bot = niobot.NioBot(...)


@bot.command()
async def my_command(ctx: niobot.Context, user: typing.Annotated[str, UserParser]):
    # typing.Annotated[real_type, parser] is a special type that allows you to specify a parser for a type.
    # In your linter, `user` will be `str`, not `UserParser`.
    await ctx.respond("User ID: {!s}".format(user))
```

### What if I need to `await` in my parser?
If you need to use asynchronous functions in your parser, you can simply return the coroutine in \_\_call__, like below:

```python
class MyParser(Parser):
    async def internal_caller(self, ctx: Context, arg: Argument, value: str):
        # Do some stuff here
        await asyncio.sleep(1)  # or whatever async function you need to call
        return value

    def __call__(self, *args, **kwargs):
        return self.internal_caller(*args, **kwargs)  # this returns a coroutine.
```
By returning the unawaited coroutine, the library will intelligently detect it needs to be awaited, and will do so.

If you want to use a parser like this in your code manually, you can always use [niobot.utils.force_await][], which will
await a coroutine if it needs awaiting, or simply returns the input if it's not a coroutine.

```python
from niobot.utils import force_await
coro = MyParser()(...)
# If you're not sure if coro is a coroutine or not, you can use force_await
parsed = await force_await()
# Otherwise, simply await the result
coro = await MyParser()(...)
```

## What's the difference between Parser and StatelessParser?
Great question!

With parsers, there's often a split between complicated/customisable, and fixed parsers. For example, 
[IntegerParser](#niobot.utils.parsers.IntegerParser) is a customisable parser - You can pass options to it while
initialising it, and it will use those options to parse the input. However, on the contrary,
[BooleanParser](#niobot.utils.parsers.BooleanParser) is a fixed parser - it does not take any options, and will always
convert the input to a boolean.

Basically, `StatelessParser` never needs to access `self` while parsing. `Parser` *can*.

### Which should I choose?
If you're writing a parser that needs to be customisable and takes options, then you should use `Parser`. Otherwise,
if you don't need `self`, then you should use `StatelessParser`.
