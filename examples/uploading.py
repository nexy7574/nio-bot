import niobot
import aiohttp
import io
import shutil

bot = niobot.NioBot(
    "https://matrix.org",
    "@user:matrix.org",
    command_prefix="£"
)


@bot.command("upload")
async def upload_random_image(ctx: niobot.Context):
    """Uploads a random inspirational quote!"""
    if not shutil.which("ffprobe"):
        await ctx.respond("ffprobe is not installed! This command requires ffprobe (part of ffmpeg) to work.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.get("https://inspirobot.me/api?generate=true") as resp:
            if resp.status != 200:
                await ctx.respond("Failed to fetch image!")
                return
            url = await resp.text()
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.respond("Failed to fetch image!")
                    return
                with open("./tmp-image.png", "w+") as file:
                    file.write(await resp.read())
                attachment = await niobot.MediaAttachment.from_file("./tmp-image.png")
                await ctx.respond("Here's your image!", file=attachment)


bot.run(password="my_password")
