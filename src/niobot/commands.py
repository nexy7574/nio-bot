import inspect
import logging
import os
import typing
import warnings
from collections.abc import Callable

import nio

from .context import Context
from .exceptions import *

if typing.TYPE_CHECKING:
    from .client import NioBot


__all__ = ("Command", "command", "event", "Module", "Argument", "check")

_T = typing.TypeVar("_T")


class Argument:
    """
    Represents a command argument.

    ??? example
        ```py
        from niobot import NioBot, command, Argument

        bot = NioBot(...)

        @bot.command("echo")
        def echo(ctx: niobot.Context, message: str):
            await ctx.respond(message)

        bot.run(...)
        ```

    :param name: The name of the argument. Will be used to know which argument to pass to the command callback.
    :param arg_type: The type of the argument (e.g. str, int, etc. or a custom type)
    :param description: The description of the argument. Will be shown in the auto-generated help command.
    :param default: The default value of the argument
    :param required: Whether the argument is required or not. Defaults to True if default is ..., False otherwise.
    """

    def __init__(
        self,
        name: str,
        arg_type: _T,
        *,
        description: typing.Optional[str] = None,
        default: typing.Any = ...,
        required: bool = ...,
        parser: typing.Callable[["Context", "Argument", str], typing.Optional[_T]] = ...,
        **kwargs,
    ):
        if default is inspect.Parameter.default:
            default = ...
        log = logging.getLogger(__name__)
        self.name = name
        self.type = arg_type
        self.description = description
        self.default = default
        self.required = required
        if self.required is ...:
            self.required = default is ...
            self.default = None
        self.extra = kwargs
        self.parser = parser

        if self.parser is ...:
            from .utils import BUILTIN_MAPPING

            if self.type in BUILTIN_MAPPING:
                log.debug("Using builtin parser %r for %r", self.type, self)
                self.parser = BUILTIN_MAPPING[self.type]
            else:
                for base in inspect.getmro(self.type):
                    if base in BUILTIN_MAPPING:
                        log.debug("Using builtin parser %r for %s due to being a subclass", base, self.type)
                        self.parser = BUILTIN_MAPPING[base]
                        break
                else:
                    log.debug("Using default parser for %s", self.type)
                    self.parser = self.internal_parser
        else:
            from .utils import BUILTIN_MAPPING

            if self.parser not in BUILTIN_MAPPING:
                from .utils import Parser

                # not a basic type (such as int, str, etc.) - ensure it subclasses Parser.
                if not issubclass(type(self.parser), Parser):
                    # raise TypeError(
                    #     "parser must be a subclass of niobot.utils.Parser, or a builtin type (e.g. str, int, etc.)"
                    # )
                    warnings.warn(
                        DeprecationWarning(
                            "custom parsers must be a subclass of niobot.utils.Parser. The old parsing methods have"
                            " been deprecated in favour of uniform ABC-inherited parsers. This will be an error after"
                            " v1.2.0"
                        )
                    )

    def __repr__(self):
        return (
            "<Argument name={0.name!r} type={0.type!r} default={0.default!r} required={0.required!r} "
            "parser={0.parser!r}>".format(self)
        )

    @staticmethod
    def internal_parser(_: Context, arg: "Argument", value: str) -> typing.Optional[_T]:
        """The default parser for the argument. Will try to convert the value to the argument type."""
        try:
            return arg.type(value)
        except ValueError:
            raise CommandParserError(f"Invalid value for argument {arg.name}: {value!r}")


class Command:
    """Represents a command.

    ??? example
        !!! note
            This example uses the `command` decorator, but you can also use the [`Command`][niobot.commands.Command]
            class directly, but you
            likely won't need to, unless you want to pass a custom command class.

            All that the `@command` decorator does is create a [`Command`][niobot.commands.Command] instance and
            add it to the bot's commands,
            while wrapping the function its decorating.

        ```py
        from niobot import NioBot, command

        bot = NioBot(...)

        @bot.command("hello")
        def hello(ctx: niobot.Context):
            await ctx.respond("Hello, %s!" % ctx.message.sender)

        bot.run(...)
        ```

    :param name: The name of the command. Will be used to invoke the command.
    :param callback: The callback to call when the command is invoked.
    :param aliases: The aliases of the command. Will also be used to invoke the command.
    :param description: The description of the command. Will be shown in the auto-generated help command.
    :param disabled:
        Whether the command is disabled or not. If disabled, the command will be hidden on the auto-generated
        help command, and will not be able to be invoked.
    :param arguments:
        A list of [`Argument`][niobot.commands.Argument] instances. Will be used to parse the arguments given to the
        command.
        `ctx` is always the first argument, regardless of what you put here.
    :param usage:
        A string representing how to use this command's arguments. Will be shown in the auto-generated help.
        Do not include the command name or your bot's prefix here, only arguments.
        For example: `usage="<message> [times]"` will show up as `[p][command] <message> [times]` in the help command.
    :param hidden:
        Whether the command is hidden or not. If hidden, the command will be always hidden on the auto-generated help.
    :param greedy:
        When enabled, `CommandArgumentsError` will not be raised if too many arguments are given to the command.
        This is useful for commands that take a variable amount of arguments, and retrieve them via `Context.args`.
    """

    def __init__(
        self,
        name: str,
        callback: Callable,
        *,
        aliases: typing.Optional[list[str]] = None,
        description: typing.Optional[str] = None,
        disabled: bool = False,
        hidden: bool = False,
        greedy: bool = False,
        usage: typing.Optional[str] = None,
        arguments: typing.Optional[list[Argument]] = None,
        **kwargs,
    ):
        self.__runtime_id = os.urandom(16).hex()
        self.log = logging.getLogger(__name__)
        self.name = name
        self.callback = callback
        self.description = description
        self.disabled = disabled
        self.aliases = aliases or []
        self.checks = kwargs.pop("checks", [])
        if hasattr(self.callback, "__nio_checks__"):
            for check_func in self.callback.__nio_checks__.keys():
                self.checks.append(check_func)
        self.hidden = hidden
        self.usage = usage or None
        self.module = kwargs.pop("module", None)
        self.arguments = arguments or None
        if not self.arguments:
            if self.arguments is False:  # do not autodetect arguments
                self.arguments = []
            else:
                self.arguments = self.autodetect_args(self.callback)
        _CTX_ARG = Argument("ctx", Context, description="The context for the command", parser=lambda ctx, *_: ctx)
        self.arguments.insert(0, _CTX_ARG)
        self.arguments: list[Argument]
        self.greedy = greedy

    @staticmethod
    def autodetect_args(callback) -> list[Argument]:
        """
        Attempts to auto-detect the arguments for the command, based on the callback's signature

        :param callback: The function to inspect
        :return: A list of arguments. `self`, and `ctx` are skipped.
        """
        # We need to get each parameter's type annotation, and create an Argument for it.
        # If it has a default value, assign that default value to the Argument.
        # If the parameter is `self`, ignore it.
        # If the parameter is `ctx`, use the `Context` type.
        log = logging.getLogger(__name__)
        args = []
        for n, parameter in enumerate(inspect.signature(callback).parameters.values()):
            # If it has a parent class and this is the first parameter, skip it.
            if n == 0 and parameter.name == "self":
                log.debug("Found 'self' parameter (%r) at position %d, skipping argument detection.", parameter, n)
                continue

            if parameter.name in ["ctx", "context"] or parameter.annotation is Context:
                log.debug(
                    "Found 'context' parameter (%r) at position %d, skipping argument detection.",
                    parameter,
                    n,
                )
                continue

            # Disallow *args and **kwargs
            if parameter.kind in [inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD]:
                # Perhaps support *args as a way to take a greedy string?
                raise CommandArgumentsError("Cannot use *args or **kwargs in command callback (argument No. %d)" % n)

            if parameter.annotation is inspect.Parameter.empty:
                log.debug("Found argument %r, however no type was specified. Assuming string.", parameter)
                a = Argument(parameter.name, str, default=parameter.default)
            else:
                annotation = parameter.annotation
                if typing.get_origin(annotation) is typing.Annotated:
                    real_type, type_parser = typing.get_args(annotation)
                    log.debug(
                        "Resolved Annotated[...] (%r) to real type %r with parser %r",
                        annotation,
                        real_type,
                        type_parser,
                    )
                    a = Argument(parameter.name, real_type, default=parameter.default, parser=type_parser)
                else:
                    log.debug("Found argument %r with type %r", parameter, parameter.annotation)
                    a = Argument(parameter.name, parameter.annotation)

            if parameter.default is not inspect.Parameter.empty:
                a.default = parameter.default
                a.required = False
            args.append(a)
        log.debug("Automatically detected the following arguments: %r", args)
        return args

    def __hash__(self):
        return hash(self.__runtime_id)

    def __eq__(self, other):
        """Checks if another command's runtime ID is the same as this one's"""
        if isinstance(other, Command):
            return self.__runtime_id == other.__runtime_id
        else:
            return False

    def __repr__(self):
        return "<Command name={0.name!r} aliases={0.aliases} disabled={0.disabled}>".format(self)

    def __str__(self):
        return self.name

    @property
    def display_usage(self) -> str:
        """Returns the usage string for this command, auto-resolved if not pre-defined"""
        if self.usage:
            return self.usage
        usage = []
        req = "<{!s}>"
        opt = "[{!s}]"
        for arg in self.arguments[1:]:
            if arg.required:
                usage.append(req.format(arg.name))
            else:
                usage.append(opt.format(arg.name))
        return " ".join(usage)

    async def invoke(self, ctx: Context) -> typing.Coroutine:
        """
        Invokes the current command with the given context

        :param ctx: The current context
        :raises CommandArgumentsError: Too many/few arguments, or an error parsing an argument.
        :raises CheckFailure: A check failed
        """
        from .utils import force_await

        if self.checks:
            for chk_func in self.checks:
                name = self.callback.__nio_checks__[chk_func]
                try:
                    cr = await force_await(chk_func, ctx)
                except CheckFailure:
                    raise  # re-raise existing check failures
                except Exception as e:
                    raise CheckFailure(name, exception=e) from e
                if not cr:
                    raise CheckFailure(name)

        parsed_args = []
        if len(ctx.args) > (len(self.arguments) - 1) and self.greedy is False:
            raise CommandArgumentsError(f"Too many arguments given to command {self.name}")
        for index, argument in enumerate(self.arguments[1:]):
            argument: Argument

            if index >= len(ctx.args):
                if argument.required:
                    raise CommandArgumentsError(f"Missing required argument {argument.name}")
                parsed_args.append(argument.default)
                continue

            self.log.debug("Resolved argument %s to %r", argument.name, ctx.args[index])
            try:
                parsed_argument = argument.parser(ctx, argument, ctx.args[index])
                if inspect.iscoroutine(parsed_argument):
                    parsed_argument = await parsed_argument
            except Exception as e:
                error = f"Error while parsing argument {argument.name}: {e}"
                raise CommandArgumentsError(error) from e
            parsed_args.append(parsed_argument)

        parsed_args = [ctx, *parsed_args]
        if len(parsed_args) != len(self.arguments):
            self.log.warning(
                "Parsed arguments length does not match registered arguments length. %d processed arguments, %d "
                "arguments.",
                len(parsed_args),
                len(self.arguments),
            )
        self.log.debug("Arguments to pass: %r", parsed_args)
        if self.module:
            self.log.debug("Will pass module instance")
            return self.callback(self.module, *parsed_args)
        else:
            return self.callback(*parsed_args)

    def construct_context(
        self,
        client: "NioBot",
        room: nio.MatrixRoom,
        src_event: nio.RoomMessageText,
        invoking_prefix: str,
        meta: str,
        cls: type = Context,
    ) -> Context:
        """
        Constructs the context for the current command.

        You will rarely need to do this, the library automatically gives you a Context when a command is run.

        :param client: The current instance of the client.
        :param room: The room the command was invoked in.
        :param src_event: The source event that triggered the command. Must be `nio.RoomMessageText`.
        :param invoking_prefix: The prefix that triggered the command.
        :param meta: The invoking string (usually the command name, however may be an alias instead)
        :param cls: The class to construct the context with. Defaults to `Context`.
        :return: The constructed Context.
        """
        if not isinstance(src_event, (nio.RoomMessageText, nio.RoomMessageNotice)):
            raise TypeError("src_event must be a textual event (i.e. m.text or m.notice).")
        return cls(client, room, src_event, self, invoking_prefix=invoking_prefix, invoking_string=meta)


def command(name: typing.Optional[str] = None, **kwargs) -> Callable:
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


def check(
    function: typing.Callable[[Context], typing.Union[bool, typing.Coroutine[None, None, bool]]],
    name: typing.Optional[str] = None,
) -> Callable:
    """
    Allows you to register checks in modules.

    ```python
    @niobot.command()
    @niobot.check(my_check_func, name="My Check")
    async def my_command(ctx: niobot.Context):
        pass
    ```

    :param function: The function to register as a check
    :param name: A human-readable name for the check. Defaults to function.__name__
    :return: The decorated function.
    """

    def decorator(command_function):
        if hasattr(command_function, "__nio_checks__"):
            command_function.__nio_checks__[function] = name or function.__name__
        else:
            command_function.__nio_checks__ = {function: name or function.__name__}
        return command_function

    decorator.internal = function
    return decorator


def event(name: str = None) -> Callable:
    """
    Allows you to register event listeners in modules.

    :param name: the name of the event (no `on_` prefix)
    :return:
    """

    def decorator(func):
        nonlocal name
        name = name or func.__name__
        func.__nio_event__ = {"function": func, "name": name, "_module_instance": None}
        return func

    return decorator


class Module:
    """
    Represents a module.

    A module houses a set of commands and events, and can be used to modularise your bot, and organise commands and
    their respective code into multiple files and classes for ease of use, development, and maintenance.

    :ivar bot: The bot instance this module is mounted to.
    """

    __is_nio_module__ = True

    def __init__(self, bot: "NioBot"):
        self.bot = bot

    @property
    def client(self) -> "NioBot":
        warnings.warn(DeprecationWarning("Module.client is deprecated. Please use Module.bot instead."))
        return self.bot

    @client.setter
    def client(self, value: "NioBot"):
        self.bot = value

    def list_commands(self) -> typing.Generator[Command, None, None]:
        for _, potential_command in inspect.getmembers(self):
            if hasattr(potential_command, "__nio_command__"):
                yield potential_command.__nio_command__

    def list_events(self):
        for _, potential_event in inspect.getmembers(self):
            if hasattr(potential_event, "__nio_event__"):
                yield potential_event.__nio_event__

    def _event_handler_callback(self, function):
        # Due to the fact events are less stateful than commands, we need to manually inject self for events
        async def wrapper(*args, **kwargs):
            return await function(self, *args, **kwargs)

        return wrapper

    def __setup__(self):
        """Setup function called once by NioBot.mount_module(). Mounts every command discovered."""
        for cmd in self.list_commands():
            cmd.module = self
            logging.getLogger(__name__).debug("Discovered command %r in %s.", cmd, self.__class__.__name__)
            self.bot.add_command(cmd)

        for _event in self.list_events():
            _event["_module_instance"] = self
            self.bot.add_event_listener(_event["name"], self._event_handler_callback(_event["function"]))

    def __teardown__(self):
        """Teardown function called once by NioBot.unmount_module(). Removes any command that was mounted."""
        for cmd in self.list_commands():
            self.bot.remove_command(cmd)
        del self
