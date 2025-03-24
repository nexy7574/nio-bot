import json
import logging
import niobot

logging.basicConfig(level=logging.DEBUG)


with open("./credentials.json") as fd:
    CREDENTIALS = json.load(fd)


bot = niobot.NioBot(
    CREDENTIALS["homeserver"],
    CREDENTIALS["user_id"],
    None,
    "./store",
    command_prefix="!",
    case_insensitive=True,
    owner_id=CREDENTIALS.get("owner_id")
)

@bot.command()
async def echo(ctx: niobot.Context, *, msg: str):
    await ctx.respond(msg)


bot.run(access_token=CREDENTIALS["token"])
