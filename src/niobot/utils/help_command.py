import re
import textwrap
import typing

from niobot.exceptions import CheckFailure

if typing.TYPE_CHECKING:
    from ..commands import Command
    from ..context import Context


__all__ = ("DefaultHelpCommand",)


class DefaultHelpCommand:
    """
    The default help command for NioBot.

    This is a very basic help command which lists available commands, their arguments, and a short descrption,
    and allows for further information by specifying the command name as an argument.
    """

    def __init__(self):
        pass

    @staticmethod
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

    @staticmethod
    def format_command_name(command: "Command") -> str:
        """Formats the command name with its aliases if applicable"""
        if not command.aliases:
            return command.name
        else:
            return "[{}]".format("|".join([command.name, *command.aliases]))

    def format_command_line(self, prefix: str, command: "Command") -> str:
        """Formats a command line, including name(s) & usage."""
        name = self.format_command_name(command)
        start = f"{prefix}{name}"
        if command.display_usage:
            start += " " + command.display_usage.strip().replace("\n", "")

        return start

    @staticmethod
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

    @staticmethod
    def get_long_description(command: "Command") -> str:
        """Gets the full help text for a command."""
        if not command.description:
            # Get the docstring of the callback
            description = command.callback.__doc__ or "No command description."
        else:
            description = command.description

        description = textwrap.dedent(description)

        return "\n".join("> " + x for x in description.splitlines())

    async def respond(self, ctx: "Context", command_name: str = None) -> None:
        """Displays help information about available commands"""
        lines = []
        prefix = ctx.invoking_prefix or "%prefix%"
        command = None
        if command_name is not None:
            command = ctx.bot.get_command(command_name.casefold())

        if command_name is None:
            added = []
            # Display global help.
            for command in sorted(ctx.client.commands.values(), key=lambda c: c.name):
                if command in added or command.disabled is True:
                    continue  # command is disabled.
                try:
                    await command.can_run(ctx)
                except CheckFailure:
                    continue  # user cannot run command
                display = self.format_command_line(prefix, command)
                description = self.get_short_description(command)
                lines.append("* `{}`: {}".format(display, description))
                added.append(command)
            await ctx.respond("\n".join(lines))
        elif command is None:
            return await ctx.respond("No command with the name %r found." % (self.clean_output(command_name)))
        else:
            display = self.format_command_line(prefix, command)
            description = self.get_long_description(command)
            lines = ["* {}:".format(display), *description.splitlines()]
            await ctx.respond(self.clean_output("\n".join(lines)))
