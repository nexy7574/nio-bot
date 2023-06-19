import logging
import inspect
import os

import nio
import typing

from .context import Context

if typing.TYPE_CHECKING:
    from .client import NioBot


__all__ = (
    "Command",
    "command",
    "event",
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
        self.__runtime_id = os.urandom(16).hex()
        self.name = name
        self.callback = callback
        self.description = description
        self.disabled = disabled
        self.aliases = aliases or []
        self.usage = kwargs.pop("usage", None)
        self.module = kwargs.pop("module", None)

    def __hash__(self):
        return hash(self.__runtime_id)

    def __eq__(self, other):
        if isinstance(other, Command):
            return self.__runtime_id == other.__runtime_id
        else:
            return False

    def __repr__(self):
        return "<Command name={0.name} aliases={0.aliases} disabled={0.disabled}>".format(self)

    def __str__(self):
        return self.name

    def invoke(self, ctx: Context):
        if self.module:
            return self.callback(self.module, ctx)
        else:
            return self.callback(ctx)

    def construct_context(
            self,
            client: "NioBot",
            room: nio.MatrixRoom,
            src_event: nio.RoomMessageText,
            meta: str
    ) -> Context:
        return Context(client, room, src_event, self, invoking_string=meta)


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


def event(name: str) -> callable:
    """
    Allows you to register event listeners in modules.

    :param name: the name of the event (no on_ prefix)
    :return:
    """
    def decorator(func):
        func.__nio_event__ = {
            "function": func,
            "name": name,
            "_module_instance": None
        }
        return func
    return decorator


class Module:
    __is_nio_module__ = True

    def __init__(self, bot: "NioBot"):
        self.bot = self.client = bot
        self.log = logging.getLogger(__name__)

    def list_commands(self):
        for _, potential_command in inspect.getmembers(self):
            if hasattr(potential_command, "__nio_command__"):
                yield potential_command.__nio_command__

    def list_events(self):
        for _, potential_event in inspect.getmembers(self):
            if hasattr(potential_event, "__nio_event__"):
                yield potential_event.__nio_event__

    async def _event_handler_callback(self, function):
        # Due to the fact events are less stateful than commands, we need to manually inject self for events
        async def wrapper(*args, **kwargs):
            return await function(self, *args, **kwargs)
        return wrapper

    def __setup__(self):
        """Setup function called once by NioBot.mount_module(). Mounts every command discovered."""
        for cmd in self.list_commands():
            cmd.module = self
            logging.getLogger(__name__).info("Discovered command %r in %s.", cmd, self.__class__.__name__)
            self.bot.add_command(cmd)

        for _event in self.list_events():
            _event["_module_instance"] = self
            self.bot.add_event(_event["name"], self._event_handler_callback(_event["function"]))

    def __teardown__(self):
        """Teardown function called once by NioBot.unmount_module(). Removes any command that was mounted."""
        for cmd in self.list_commands():
            self.bot.remove_command(cmd)
        del self
