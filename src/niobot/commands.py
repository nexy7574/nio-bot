import logging
import inspect

import nio
import typing

from .context import Context

if typing.TYPE_CHECKING:
    from .client import NioBot


__all__ = (
    "Command",
    "command",
    "Module"
)


class Command:
    """Represents a command."""
    def __init__(
            self,
            name: str,
            callback: callable,
            *,
            aliases: list[str] = None,
            description: str = None,
            disabled: bool = False,
            **kwargs
    ):
        self.name = name
        self.callback = callback
        self.description = description
        self.disabled = disabled
        self.aliases = aliases or []
        self.usage = kwargs.pop("usage", None)

    def __repr__(self):
        return "<Command name={0.name} aliases={0.aliases} disabled={0.disabled}>".format(self)

    def __str__(self):
        return self.name

    def construct_context(
            self,
            client: "NioBot",
            room: nio.MatrixRoom,
            event: nio.RoomMessageText,
            meta: str
    ) -> Context:
        return Context(client, room, event, self, invoking_string=meta)


def command(name: str = None, **kwargs) -> callable:
    """
    Allows you to register commands later on, by loading modules.

    This differs from NioBot.command() in that commands are not automatically added, you need to load them with
    bot.mount_module
    :param name: The name of the command. Defaults to function.__name__
    :param kwargs: Any key-words to pass to Command
    :return:
    """
    cls = kwargs.pop("cls", Command)

    def decorator(func):
        nonlocal name
        name = name or func.__name__
        cmd = cls(name, func, **kwargs)
        func.__nio_command__ = cmd
        return func

    return decorator


class Module:
    __is_nio_module__ = True

    def __init__(self, bot: "NioBot"):
        self.bot = self.client = bot
        self.log = logging.getLogger(__name__)

    def list_commands(self, mounted_only: bool = False):
        for _, potential_command in inspect.getmembers(self):
            self.log.debug("Found member: %r", potential_command)
            if inspect.isfunction(potential_command):
                self.log.debug("%r is a function", potential_command)
                if hasattr(potential_command, "__nio_command__"):
                    self.log.debug("%r is a command!", potential_command)
                    if mounted_only:
                        if not self.bot.get_command(potential_command.__nio_command__.name):
                            continue
                    yield potential_command.__nio_command__
                else:
                    self.log.debug("%r is not a command.", potential_command)

    def __setup__(self):
        """Setup function called once by NioBot.mount_module(). Mounts every command discovered."""
        for cmd in self.list_commands():
            logging.getLogger(__name__).info("Discovered command %r in %s.", cmd, self.__class__.__name__)
            self.bot.add_command(cmd)

    def __teardown__(self):
        """Teardown function called once by NioBot.unmount_module(). Removes any command that was mounted."""
        for cmd in self.list_commands():
            self.bot.remove_command(cmd)
