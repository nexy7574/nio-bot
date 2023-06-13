import niobot
import time


bot = niobot.NioBot(
    "https://matrix.org",
    "@my_user_id:matrix.org",  # remember, you can use any account here. It doesn't have to be special.
    "my_bot_name",
    store_path="/tmp",  # store state in a temporary directory, we don't really need it for these examples.
    command_prefix="!",
    owner_id="@my_user_id:matrix.org"  # this is the user ID of the bot's owner. It's used for the owner-only commands.
)


@bot.command()
async def ping(ctx: niobot.Context):
    """Shows the latency between the bot and the homeserver, in milliseconds."""
    server_timestamp_seconds = ctx.message.server_timestamp / 1000  # convert from milliseconds to seconds
    latency = time.time() - server_timestamp_seconds  # the time between now and the server timestamp
    await ctx.reply(f"Pong! {latency * 1000:.2f}ms")  # convert to ms, and reply to the user


@bot.command()
async def info(ctx: niobot.Context):
    """Shows information about the currently running instance."""
    await ctx.reply(f"Bot owner: {ctx.client.owner_id}\n"
                    f"Bot user ID: {ctx.client.user_id}\n"
                    f"Bot homeserver: {ctx.client.homeserver}\n"
                    f"Bot command prefix: {ctx.client.command_prefix}\n"
                    f"Bot command count: {len(ctx.client.commands)}\n"
                    f"Bot module count: {len(ctx.client.modules)}\n"
                    f"Bot uptime: {time.time() - ctx.client.start_time:,.0f} seconds")

bot.run(password="my_account_password")  # it is recommended to use an access token instead. See access_token.py
