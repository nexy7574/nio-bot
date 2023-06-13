import nio
import textwrap
import typing

if typing.TYPE_CHECKING:
    from ..client import NioBot
    from ..context import Context


async def help_command(ctx: "Context"):
    """Displays help text"""
    lines = []
    if not ctx.args:
        for command in ctx.client._commands.values():
            name = command.name
            display_names = [name]
            if command.aliases:
                display_names += command.aliases

            display_name = "[{}]".format('|'.join(display_names))
            description = command.description or command.__doc__
            if description:
                description = description.splitlines()[0]
                description = textwrap.shorten(description, 100, replace_whitespace=True, drop_whitespace=True)
            else:
                description = 'No description.'
            lines.append("* {}{}: {}".format(ctx.client.command_prefix, display_name, description))
        await ctx.reply("\n".join(lines))
    else:
        command = ctx.client.get_command(ctx.args[0])
        if not command:
            return await ctx.reply("No command with that name found!")
        name = command.name
        display_names = [name]
        if command.aliases:
            display_names += command.aliases
        display_name = "[{}]".format('|'.join(display_names))
        description = command.description or command.__doc__
        if description:
            description = description.splitlines()
        else:
            description = ['No description.']
        lines = [
            "* {}{}:".format(ctx.client.command_prefix, display_name),
        ]
        for desc_line in description:
            lines.append(">\t" + desc_line)
        await ctx.reply("\n".join(lines))
