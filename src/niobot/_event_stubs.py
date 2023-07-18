# THIS FILE IS NOT MEANT TO BE IMPORTED! IT DOES NOT FEATURE ANY ACTUAL CODE! ITS JUST STUBS!!!
# This file is written so that mkdocs can auto-generate an event reference.
import typing as t

if t.TYPE_CHECKING:
    from . import SyncResponse, MatrixRoom, RoomMessageText, Context, CommandError


async def ready(result: "SyncResponse") -> t.Optional[t.Any]:
    """
    An event that is fired when the bot's first `sync()` is completed.

    This indicates that the bot successfully logged in, synchronised with the server, and is ready to receive events.

    :param result: The response from the sync.
    """
    ...


async def message(room: "MatrixRoom", event: "RoomMessageText") -> t.Optional[t.Any]:
    """
    An event that is fired when the bot receives a message in a room that it is in.

    This event is dispatched *before* commands are processed, and as such the convenient [niobot.Context][] is
    unavailable.

    !!! tip
        If you want to be able to use the [niobot.Context][] in your event handlers, you should use the
        `command` event instead.

        Furthermore, if you want more fine-grained control over how commands are parsed and handled, you should
        *override* [niobot.NioBot.process_message][] instead of using the `message` event.

    :param room: The room that the message was received in.
    :param event: The raw event that triggered the message.
    """
    ...


async def command(ctx: "Context") -> t.Optional[t.Any]:
    """
    This event is dispatched once a command is finished being prepared, and is about to be invoked.

    This event is dispatched *after* the `message` event, but *before* `command_complete` and `command_error`.

    This event features the original context, which can be used to access the message, the command, and the arguments.

    :param ctx: The context of the command.
    """
    ...


async def command_complete(ctx: "Context", result: t.Any) -> t.Optional[t.Any]:
    """
    This event is dispatched after a command has been invoked, and has completed successfully.

    This event features the context, which can be used to access the message, the command, and the arguments.

    :param ctx: The context of the command.
    :param result: The result of the command (the returned value of the callback)
    """
    ...


async def command_error(ctx: "Context", error: "CommandError") -> t.Optional[t.Any]:
    """
    This event is dispatched after a command has been invoked, and has completed with an error.

    This event features the context, which can be used to access the message, the command, and the arguments.

    ??? example "Getting the original error"
        As the error is wrapped in a [niobot.CommandError][], you can access the original error by accessing the
        [`CommandError.original`][niobot.CommandError.original] attribute.

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
    ...
