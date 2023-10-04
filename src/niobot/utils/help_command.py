import re
import textwrap
import typing
import warnings

if typing.TYPE_CHECKING:
    from ..commands import Command
    from ..context import Context


__all__ = (
    "format_command_name",
    "format_command_line",
    "get_short_description",
    "get_long_description",
    "help_command_callback",
    "default_help_command",
    "clean_output",
)


def clean_output(
    text: str,
    *,
    escape_user_mentions: bool = True,
    escape_room_mentions: bool = True,
    escape_room_references: bool = False,
    escape_all_periods: bool = False,
    escape_all_at_signs: bool = False,
    escape_method: typing.Optional[typing.Callable[[str], str]] = None,
) -> str:
    """
    Escapes given text and sanitises it, ready for outputting to the user.

    This should always be used when echoing any sort of user-provided content, as we all know there will be some
    annoying troll who will just go `@room` for no apparent reason every 30 seconds.

    !!! danger "Do not rely on this!"
        This function is not guaranteed to escape all possible mentions, and should not be relied upon to do so.
        It is only meant to be used as a convenience function for simple commands.

    :param text: The text to sanitise
    :param escape_user_mentions: Escape all @user:homeserver.tld mentions
    :param escape_room_mentions: Escape all @room mentions
    :param escape_room_references: Escape all #room:homeserver.tld references
    :param escape_all_periods: Escape all literal `.` characters (can be used to escape all links)
    :param escape_all_at_signs: Escape all literal `@` characters (can be used to escape all mentions)
    :param escape_method: A custom escape method to use instead of the built-in one
    (which just wraps characters in `\\u200b`)
    :return: The cleaned text
    """
    if escape_method is None:

        def default_escape_method(x: str) -> str:
            return "\u200b".join(x.split())

        escape_method = default_escape_method

    if escape_user_mentions:
        text = re.sub(r"@([A-Za-z0-9\-_=+./]+):([A-Za-z0-9\-_=+./]+)", escape_method("@\\1:\\2"), text)
    if escape_room_mentions:
        text = text.replace("@room", escape_method("@room"))
    if escape_room_references:
        text = re.sub(r"#([A-Za-z0-9\-_=+./]+):([A-Za-z0-9\-_=+./]+)", escape_method("#\\1:\\2"), text)
    if escape_all_periods:
        text = text.replace(".", escape_method("."))
    if escape_all_at_signs:
        text = text.replace("@", escape_method("@"))

    return text


def format_command_name(command: "Command") -> str:
    """Formats the command name with its aliases if applicable"""
    if not command.aliases:
        return command.name
    else:
        return "[{}]".format("|".join([command.name, *command.aliases]))


def format_command_line(prefix: str, command: "Command") -> str:
    """Formats a command line, including name(s) & usage."""
    name = format_command_name(command)
    start = f"{prefix}{name}"
    start += " " + command.display_usage.strip().replace("\n", "")

    return start


def get_short_description(command: "Command") -> str:
    """Generates a short (<100 characters) help description for a command."""
    if not command.description:
        # Get the docstring of the callback
        if command.callback.__doc__:
            # De-indent
            doc = textwrap.dedent(command.callback.__doc__)
        else:
            doc = "No command description."
        description = doc
    else:
        description = command.description

    line = description.splitlines()[0]
    return textwrap.shorten(line, width=100)


def get_long_description(command: "Command") -> str:
    """Gets the full help text for a command."""
    if not command.description:
        # Get the docstring of the callback
        description = command.callback.__doc__ or "No command description."
    else:
        description = command.description

    return "\n".join("> " + x for x in description.splitlines())


async def default_help_command(ctx: "Context"):
    """Displays help text"""
    lines = []
    prefix = ctx.invoking_prefix or "[p]"
    if not ctx.args:
        added = []
        # Display global help.
        # noinspection PyProtectedMember
        for command in ctx.client._commands.values():
            if command in added or command.disabled is True:
                continue
            display = format_command_line(prefix, command)
            description = get_short_description(command)
            lines.append("* `{}`: {}".format(display, description))
            added.append(command)
        await ctx.respond("\n".join(lines))
    else:
        command = ctx.client.get_command(ctx.args[0])
        if not command:
            return await ctx.respond("No command with that name found!")

        display = format_command_line(prefix, command)
        description = get_long_description(command)
        lines = ["* {}:".format(display), *description.splitlines()]
        await ctx.respond(clean_output("\n".join(lines)))


def help_command_callback(ctx: "Context"):
    """Default help command callback"""
    warnings.warn(
        "help_command_callback is deprecated and will be removed in v1.2.0, please use default_help_command instead",
        DeprecationWarning,
    )
    return default_help_command(ctx)
