# THIS FILE IS NOT MEANT TO BE IMPORTED! IT DOES NOT FEATURE ANY ACTUAL CODE! ITS JUST STUBS!!!
# This file is written so that mkdocs can auto-generate an event reference.
import typing as t

if t.TYPE_CHECKING:
    from . import CommandError, Context, Event, MatrixRoom, RoomMessage, SyncResponse


async def event_loop_running() -> t.Optional[t.Any]:
    """An event that is fired once the event loop is running.

    !!! tip "You should use this event to perform any startup tasks."
        This event is fired before the bot logs in, and before the first `sync()` is performed.

        This means that if, for example, you wanted to initialise a database, or make some HTTP request in a module,
        You can @[nio]bot.event("event_loop_running") do it here.

        ??? example "Initialising a database in a module"
            ```python
            import niobot
            import aiosqlite

            class MyModule(niobot.Module):
                def __init__(self, bot):
                    super().__init__(bot)
                    self.db = None

                @niobot.event("event_loop_running")
                async def event_loop_running(self):
                    self.db = await aiosqlite.connect("mydb.db")
                    await self.db.execute(...)
                    await self.db.commit
            ```
    """


async def ready(result: "SyncResponse") -> t.Optional[t.Any]:
    """An event that is fired when the bot's first `sync()` is completed.

    This indicates that the bot successfully logged in, synchronised with the server, and is ready to receive events.

    :param result: The response from the sync.
    """


async def message(room: "MatrixRoom", event: "RoomMessage") -> t.Optional[t.Any]:
    """An event that is fired when the bot receives a message in a room that it is in.

    This event is dispatched *before* commands are processed, and as such the convenient [niobot.Context][] is
    unavailable.

    !!! danger "Not every message is a text message"
        As of v1.2.0, the `message` event is dispatched for every decrypted message type, as such
        including videos, images, audio, and text. Prior for v1.2.0, this was only dispatched for
        text messages.

        Please check either the type of the event (i.e. `isinstance(event, niobot.RoomMessageText)`)
        or the `event.source["content"]["msgtype"]` to determine the type of the message.

    !!! tip
        If you want to be able to use the [niobot.Context][] in your event handlers, you should use the
        `command` event instead.

        Furthermore, if you want more fine-grained control over how commands are parsed and handled, you should
        *override* [niobot.NioBot.process_message][] instead of using the `message` event.

    :param room: The room that the message was received in.
    :param event: The raw event that triggered the message.
    """


async def command(ctx: "Context") -> t.Optional[t.Any]:
    """This event is dispatched once a command is finished being prepared, and is about to be invoked.

    This event is dispatched *after* the `message` event, but *before* `command_complete` and `command_error`.

    This event features the original context, which can be used to access the message, the command, and the arguments.

    :param ctx: The context of the command.
    """


async def command_complete(ctx: "Context", result: t.Any) -> t.Optional[t.Any]:
    """This event is dispatched after a command has been invoked, and has completed successfully.

    This event features the context, which can be used to access the message, the command, and the arguments.

    :param ctx: The context of the command.
    :param result: The result of the command (the returned value of the callback)
    """


async def command_error(ctx: "Context", error: "CommandError") -> t.Optional[t.Any]:
    """This event is dispatched after a command has been invoked, and has completed with an error.

    This event features the context, which can be used to access the message, the command, and the arguments.

    ??? example "Getting the original error"
        As the error is wrapped in a [niobot.CommandError][], you can access the original error by accessing the
        [`CommandError.original`][niobot.exceptions.CommandError] attribute.

        ```python
        @bot.event("command_error")
        async def on_command_error(ctx, error):
            original_error = error.original
            print("Error:", original_error)
        ```

    It is encouraged that you inform the end user about an error that has occurred, as by default the error is simply
    logged to the console. Don't forget, you've got the whole `Context` instance - use it!

    :param ctx: The context of the command.
    :param error: The error that was raised.
    """


async def raw(room: "MatrixRoom", event: "Event") -> t.Optional[t.Any]:
    """This is a special event that is handled when you directly pass a `niobot.Event` to `on_event`.

    You cannot listen to this in the traditional sense of "on_event('name')" as it is not a named event.
    But, this extensibility allows you to listen directly for events not covered by the library.

    ??? example
        The below code will listen directly for the redaction event and will print out the redaction details.

        See [the nio events](https://matrix-nio.readthedocs.io/en/latest/nio.html#module-nio.events) documentation
        for more details and a list of available events.x

        ```python
        import niobot

        @bot.on_event(niobot.RedactionEvent)  # listen for redactions
        async def on_redaction(room, event):
            print(f"{event.sender} redacted {event.redacts} for {event.reason!r} in {room.display_name}")
        ```
    """
