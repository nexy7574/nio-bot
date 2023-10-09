# Typing helper

This utility module contains one tool: the `Typing` class. It is internally used in the `<send/edit/delete>_message`
functions of `NioBot`, but you can use it at any point to send typing events to the chat.

## Usage

::: niobot.utils.Typing

!!! warning
    Nesting `Typing` instances for one specific room is a bad idea, as when each instance is exited, it stops typing
    for the given room. For example, the below will not work as expected:

    ```py
    from niobot import NioBot, utils

    bot = NioBot(...)

    @bot.command()
    async def ping(ctx):
        async with utils.Typing(ctx.client, ctx.room.room_id):
            await ctx.respond("Pong!")

    bot.run(...)
    ```

    This will not work because `Context.respond` calls `NioBot.send_message`, and `NioBot.send_message` creates its own
    `Typing` instance.
    Once `ctx.respond` returns, the internal `Typing` instance is destroyed, and the typing event is stopped, as is
    the behaviour of [exiting the context manager](#niobot.utils.typing.Typing.__aexit__). This means that either
    if on the loop, the upper-most `utils.Typing` instance will simply just create a new typing notification,
    or will not (especially if `persistent` was set to `False`). This breaks the whole persistence of typing.

    ??? info "If you want to use `Typing` to show that you're processing something:"
        If you want to use `Typing` to show a user that your bot is "thinking", or similar, you should make sure you
        exit the instance before responding. For example:

        ```py
        from niobot import NioBot, Typing
        import httpx
        
        bot = NioBot(...)

        @bot.command()
        async def process(ctx):
            """Spends a worryingly long time making a network request."""
            async with Typing(ctx.client, ctx.room.room_id):
                await httpx.get("https://example.com")
            await ctx.respond("Done!")
        ```

        Be aware that this will cause a momentary blip in the `xyz is typing` status, but this is unavoidable, simply
        due to the semi-stateless nature of this context wrapper

        A potential future solution would be to implement some funky internal lock mechanism and/or just prevent
        nested `Typing` instances, but this is not a priority at the moment.
