# Direct Messages

!!! tip "New in version 1.1.0b2"
    This feature was added in version 1.1.0b2 - `pip install niobot>=1.1.0b2`

In Matrix, 
[Direct Messages are a bit of a loose concept](https://spec.matrix.org/v1.8/client-server-api/#direct-messaging).
In short, a "direct message" in Matrix is more of a room, except with initially only two members, and a special flag,
`is_direct`, set to `true` in the `invite` event.

However, when you join a direct room, or flag a room as direct in a client, this information is stored in account data,
on the homeserver. This means that your homeserver will keep track of rooms that you're in that're flagged as "direct".

!!! danger "Direct does not mean one-to-one!"
    Direct rooms are not necessarily one-to-one. They can have more than two members, and they can be group chats.

    The only thing that makes a room "direct" is the `is_direct` flag in the `invite` event.

    This means that if you want to send a message to a user, you should check if the direct room you've chosen contains
    only two members. If not, look for another, or create one.

## How do I send DMs in NioBot?
NioBot handles DMs mostly transparently.

In base `matrix-nio`, trying to use `AsyncClient.room_send` and passing a user as the `room_id` will result in an error.
You'd probably expect it to send a message to that user, so NioBot does just that!

With a bit of magic, NioBot will automatically create a direct room with the user, and send the message there.
In addition, if there's already a direct room stored in account data, NioBot will use the first one it finds.

Take this example:

```python
import niobot

bot = niobot.NioBot(...)


@bot.command("dm")
async def send_dm(ctx: niobot.Context):
    """Sends you a direct message!"""
    await bot.send_message(ctx.message.sender, "Hello, world!")
```

First, NioBot checks to see if there's a direct room stored in account data. If there is, it'll use that.
If not, however, it will create one, and invite the user.

And that's it! Its really that simple!

## Getting and creating direct rooms
If you want to use direct rooms outside of sending messages, you can use [niobot.NioBot.get_dm_rooms][], and
[niobot.NioBot.create_dm_room][].

For example:
```python
import niobot

bot = niobot.NioBot(...)


@bot.command("get-dm-rooms")
async def get_dm_room(ctx: niobot.Context):
    """Gets the direct room with the user."""
    rooms = await bot.get_dm_rooms(ctx.message.sender)

    if not rooms:
        await ctx.respond("You don't have any direct rooms!")
        return

    rooms_text = "\n".join([f"* https://matrix.to/#/{room_id}" for room_id in rooms])
    await ctx.respond(f"Your {len(rooms):,} direct rooms:\n\n{rooms_text}")


@bpt.command("create-dm-room")
async def create_dm_room(ctx: niobot.Context):
    """Creates a direct room with the user."""
    response = await bot.create_dm_room(ctx.message.sender)
    await ctx.respond(f"Created direct room: https://matrix.to/#/{response.room_id}")
```

In this example, `get-dm-rooms` would return a count, alongside a list, of every DM room the client shares with the
user. `create-dm-room` would create a new direct room with the user, and return the room link.

The user would've already been automatically invited to the room when it was created, so there's no need to send an
invitation separately.
