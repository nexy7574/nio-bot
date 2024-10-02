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
        mentions.room = True
    # can also be constructed as `mentions = Mentions(true, ctx.message.sender)
    content = f"Hello {ctx.message.sender}, from @room!"
    await ctx.respond("Hello, " + ctx.message.sender, mentions=mentions)
    # This message will ping ctx.message.sender. If `ping_room` is `True`, it will also ping the room, otherwise,
    # it will only render it.
```

## How automatic parsing works

As this is a feature that may be unexpected to some users, `nio-bot` will automatically parse mentions if:

1. `NioBot.default_parse_mentions` is `True` (default) **AND**
2. `NioBot.send_message` is not given an explicit `mentions=` argument **AND**
3. The message has a `content` that is not empty.

In this case, niobot will scan through the message, enable the `@room` ping if that string is detected in the string,
and will attempt to match any user mentions in the message.
This is not foolproof, and the best way to ensure mentions are parsed correctly is to manually pass the mentions
you want to the `Mentions` object.

### Disabling mentions

If you want to send a message that contains @mentions, but don't want them to *actually* mention anyone, you can pass
`mentions=niobot.Mentions()` in `send_message`.
This will still *render* the mentions on the client (usually), but rest assured it did not actually mention them
(i.e. they will not have received a notification).

!!! danger "You cannot create a mention that is not also rendered"
    To mention someone, you must include that in your textual body too, **not just in the mentions object**.
    If you only mention someone via the `Mentions` object, it will not work.
