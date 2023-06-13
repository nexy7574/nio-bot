import nio
import textwrap
import typing

if typing.TYPE_CHECKING:
    from ..client import NioBot
    from ..context import Context
    from ..commands import Command


def format_command_name(command: "Command") -> str:
    """Formats the command name with its aliases if applicable"""
    if not command.aliases:
        return command.name
    else:
        return "[{}]".format(
            "|".join([command.name, *command.aliases])
        )


def format_command_line(prefix: str, command: Command) -> str:
    """Formats a command line, including name(s) & usage."""
    name = format_command_name(command)
    start = "{}{}".format(prefix, name)
    if command.usage:
        start += " " + command.usage.strip().replace("\n", "")

    return start


def get_short_description(command: "Command") -> str:
    """Generates a short (<100 characters) help description for a command."""
    if not command.description:
        # Get the docstring of the callback
        description = command.callback.__doc__ or "No command description."
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

    return "\n".join(
        "> " + x for x in description.splitlines()
    )


async def help_command(ctx: "Context"):
    """Displays help text"""
    lines = []
    if not ctx.args:
        # Display global help.
        # noinspection PyProtectedMember
        for command in ctx.client._commands.values():
            display = format_command_line(ctx.client.command_prefix, command)
            description = get_short_description(command)
            lines.append("* `{}`: {}".format(display, description))
        await ctx.reply("\n".join(lines))
    else:
        command = ctx.client.get_command(ctx.args[0])
        if not command:
            return await ctx.reply("No command with that name found!")

        display = format_command_line(ctx.client.command_prefix, command)
        description = get_long_description(command)
        lines = [
            "* {}:".format(display),
            *description.splitlines()
        ]
        await ctx.reply("\n".join(lines))
