# Commands

Using commands and events is the main way to interact with the bot.

## Command argument detection

One of the most powerful features of NioBot is the command argument interpretation system.
When you create a niobot command, the arguments are automatically detected, and their desired
type is inferred from the type hints in the function signature.

This means that `foo: str` will always give you a string, `bar: int` will try to give you an integer,
or throw an error if it cannot convert the user-given argument.

As of v1.2.0, you can take advantage of the keyword-only and positional args in Python.
Normally, when you specify a function like `async def mycommand(ctx, x: str)`, niobot will see
that you want an argument, x, and will do just that. It will take the user's input, and give you
the value for x. However, if the user specifies multiple words for `x`, it will only give the first one
to the function, unless the user warps the argument in "quotes".

```python
import niobot
bot = niobot.NioBot()

@bot.command()
async def mycommand(ctx, x: str):
    await ctx.respond(f"Your argument was: {x}")
```
If you ran `!mycommand hello world`, the bot would respond with `Your argument was: hello`.

With keyword-only arguments, you can make use of "greedy" arguments.
While you could previously do this by *manually* constructing the [niobot.Argument][] type,
you can now do this with the `*` syntax in Python.

```python
import niobot
bot = niobot.NioBot()

@bot.command()
async def mycommand(ctx, *, x: str):
    await ctx.respond(f"Your argument was: {x}")
```
If you ran `!mycommand hello world`, the bot would respond with `Your argument was: hello world`.

And, as for positional args, if you want to fetch a set of arguments, you can do so by specifying
`*args`. This will give you a tuple containing every whitespace-delimited argument after the command.

```python
import niobot
bot = niobot.NioBot()

@bot.command()
async def mycommand(ctx, *args: str):
    await ctx.respond(f"Your arguments were: {args}")
```
If you ran `!mycommand hello world`, the bot would respond with `Your arguments were: ('hello', 'world')`.

!!! danger "Position & KW-Only args are final and strings!"
    If you specify a keyword or positional argument, you cannot have any arguments afterwards.
    Furthermore, (currently) both of these arguments are always strings. Trying to specify
    another type will throw an error.

---

## Reference

::: niobot.commands
