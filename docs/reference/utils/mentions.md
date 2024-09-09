# Mentions

!!! info "New in v1.2.0"
    This module was added in v1.2.0, so you will not be able to use this if you are using an older version of `nio-bot`.

    See the changelog for more information.


Starting in v1.2.0, `nio-bot` now has the added functionality of [intentional mentions](https://spec.matrix.org/v1.11/client-server-api/#definition-mmentions),
which allows you to even more finely tune who is mentioned by your messages.

Previously just including `@mxid:homeserver.example` or `@room` would create mentions, but sometimes this was undesirable (for example, echoing user input (WHICH YOU SHOULD NOT DO)).

Using `Mentions`, you can now control exactly how you want mentions to be created.

::: niobot.utils.mentions

## Example

```python
from niobot import NioBot, Context, Mentions


bot = NioBot(
    homeserver="https://matrix-client.matrix.org",
    user_id="@my_user:matrix.org",
    command_prefix="!"
)

@bot.command("mention")
async def mention_command(ctx: Context, ping_room: bool = False):
    """Mentions a user."""
    mentions = Mentions()
    mentions.add_user(ctx.message.sender)
    if ping_room:
        mentions.add_room(ctx.message.room_id)
    # can also be constructed as `mentions = Mentions(true, ctx.message.sender)
    await ctx.respond("Hello, " + ctx.message.sender, mentions=mentions)
```
