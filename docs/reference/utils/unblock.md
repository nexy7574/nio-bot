# Unblock

A common problem developers encounter when working with an asyncio event loop is long blocking code.
This can be caused by a number of things, but the most common is a call to a library that is not async-aware, and has
many blocking operations (such as `requests`, or even the built-in `open()` + `read()` functions).

To alleviate this, NioBot provides an "unblock" utility, which is a simple async function that will run any blocking
code in the event loop executor, and returns the result, without pausing the event loop.
This is equivalent to `loop.run_in_executor(None, func, *args, **kwargs)`.

??? success "A good example"
    ```py
    from niobot import NioBot, command
    from niobot.utils import run_blocking

    bot = NioBot(...)


    @bot.command(name="read")
    async def read_file(ctx: Context, filename: str):
        with open(filename, "r") as f:
            contents = await run_blocking(f.read)
        await ctx.respond(contents)

    bot.run(...)
    ```
    This will read the contents of a file, without blocking the event loop, unlike the following code:

??? bug "A bad example"
    ```py
        from niobot import NioBot, command
        from niobot.utils import run_blocking
    
        bot = NioBot(...)
    
    
        @bot.command(name="read")
        async def read_file(ctx: Context, filename: str):
            with open(filename, "r") as f:
                contents = f.read()
            await ctx.respond(contents)
    
        bot.run(...)
    ```
    This example is bad because it will prevent any other event processing until `f.read()` finishes,
    which is really bad if the file is large, or the disk is slow. For example, if you read at 1mb/s, and you have
    a 10 megabyte file, you will block the event loop for approximately 10 seconds, which means your program
    cannot do anything in those ten seconds, and as such your bot will appear to be non-functional!

::: niobot.utils.unblocking
