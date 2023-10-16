# A simple bot - example
Let's take the following code and break it down, so that you can better understand how niobot works:

??? example
    ```python
    import niobot


    bot = niobot.NioBot(
        homeserver="https://matrix.org",
        user_id="@my_username:matrix.org",
        device_id="my_device_name",  # defaults to the easily recognisable 'nio-bot'.
        store_path="./store",  # See the 'What is the store?' section for more info.
        command_prefix="!",
        case_insensitive=True,  # means `!PING` and `!piNG` will both work and run `!ping`.
        owner_id="@owner:matrix.org",  # The user ID who owns this bot. Optional, but required for bot.is_owner(...).#
        # Here, you can pass extra options that you would usually pass to `nio.AsyncClient`. Lets pass a proxy:
        proxy="socks5://username:password@host:port"
    )


    # Now, we want to register a command. NioBot uses the decorator `@NioBot.command()` for this.
    # This decorator takes a few arguments, but the only one you'll use most of the time is `name`.
    # There are also other arguments though.
    # For now we'll register a simple `ping` command.
    @bot.command(name="ping")
    # We now need to define the function
    async def ping(ctx: niobot.Context):
        """Shows the latency between events"""
        # So a few things have happened here:
        # `async def` makes this command asynchronous. This means that it can `await` other things.
        # `ctx` is the only argument this command takes. By default, all niobot commands must take at least one argument,
        # which is the command's context.
        # We also then typehinted it with `niobot.Context`. This isn't critical to make the bot run, however if you're using
        # an IDE like PyCharm, or just a workspace editor with intellisense like Visual Studio Code, it will help you
        # to see what attributes and functions `niobot.Context` has without needing to check the documentation.
        # Anyway, lets write the command itself.
        # First, we need to measure the latency. NioBot has a handy function for this:
        latency_ms = bot.latency(ctx.message)
        # `bot.latency` measures the latency between when the event was dispatched by the server, and when the bot
        # received it. It then returns the latency in milliseconds.
        # `Context.message` is the event that triggered this command.
        # Now, we need to reply to the user.
        await ctx.respond("Pong! Latency: {:.2f}ms".format(latency_ms))
        # And that's it! We've written our first command.
        # `Context.respond` always sends a reply to the user who sent the command.
        # To send a message without a reply, you can use `NioBot.send_message`.


    # And while we're at it, we can add an event listener.
    # For this example, we'll add an event listener that tells the user if there's a command error.
    @bot.on_event("command_error")
    async def on_command_error(ctx: niobot.Context, error: Exception):
        """Called when a command raises an exception"""
        # Take a look at the event reference for more information about events.
        # Now, we can send a message to the user.
        await ctx.respond("Error: {}".format(error))


    # And while we're at it, we'll log when a user runs a command.
    @bot.on_event("command")
    async def on_command(ctx):
        print("User {} ran command {}".format(ctx.message.sender, ctx.command.name))


    # Now, we need to start our bot.
    # This is done by calling `NioBot.run()`.
    # In this example, we'll use an access token, rather than an insecure password.
    # You can get an access token through the niobot CLI:
    # $ niocli get-access-token
    # Copy the resulting access token, and then you can put it here:
    bot.run(access_token="my_access_token")
    # Bear in mind that no code will run after `bot.run`. This function will block until the bot is stopped.
    # And even when the bot is stopped, its usually with an exception, so code after `bot.run` is not guaranteed to run.
    ```
