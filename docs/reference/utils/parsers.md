# Parsers

These are a handful of built-in parsers that you can use with `niobot.Argument`.

??? quote "How do I use these?"
    To use a parser, you simply pass `parser=<function>` when creating `Argument()`.
    For example:

    ```py
    from niobot import Argument, command, NioBot
    from niobot.utils.parsers import float_parser
    
    bot = NioBot(...)
    
    @bot.command(
        name="sum", 
        arguments=[
            Argument("num1", parser=float_parser),
            Argument("num2", parser=float_parser)
        ]
    )
    async def add_numbers(ctx: Context, num1: float, num2: float):
        await ctx.respond("{!s} + {!s} = {!s}".format(num1, num2, num1 + num2))

    bot.run(...)
    ```

    While this is roughly equivalent to `Argument("num1", type=float)`, it can be helpful in cases like 
    [json_parser](#niobot.utils.parsers.json_parser) where you need to parse complex types.

!!! tip
    You can also create your own parsers! See [Creating Parsers](#creating-parsers) for more information.

::: niobot.utils.parsers

--------------------------

## Creating Parsers

??? note "The old way (pre-1.1.0)"
    Creating your own parser is actually really easy. All the library needs from you is a function that:
    
    * Takes `niobot.Context` as its first argument
      * Takes `niobot.Argument` as its second argument
      * Takes a `str`ing (the user's input) as its third argument
      * Returns a sensible value
      * Or, raises CommandArgumentsError with a helpful error message.
    
    Do all of this, and you can very easily just pass this to `Argument`!
    
    For example, if you wanted to take a `datetime`, you could write your own parser like this:
    
    ```python
    from datetime import datetime
    from niobot import Argument, command, NioBot
    
    
    def datetime_parser(ctx: Context, arg: Argument, user_input: str):
        try:
            return datetime.strptime(user_input, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise CommandArgumentsError("Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS")
    
    bot = NioBot(...)
    
    
    @bot.command(name="remindme", arguments=[Argument("time", arg_type=datetime, parser=datetime_parser)])
    async def remind_me(ctx: Context, time: datetime):
        await ctx.respond("I'll remind you at {}!".format(time.strftime("%c")))
    
    bot.run(...)
    ```

Creating custom parsers for nio-bot is really simple. All you need to do is subclass either 
[Parser][niobot.utils.parsers] or [StatelessParser][niobot.utils.parsers] and implement the `parse` method.

However, if you want some detailed information, seek [the guide](../../guides/004-creating-custom-parsers.md/)
