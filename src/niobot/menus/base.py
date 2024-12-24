import abc
import asyncio
import functools

import nio
import typing
from typing_extensions import Self

from ..context import Context

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = (
    "Menu",
    "MenuButton",
    "menu_button"
)


class MenuButton:
    def __init__(
            self,
            menu: typing.Optional["Menu"],
            *,
            annotation: str,
    ):
        self.menu = menu
        self.annotation = annotation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MenuButton):
            return False
        return self.annotation == other.annotation and (self.menu is None or self.menu == other.menu)

    def __hash__(self):
        return self.annotation, self.menu

    @abc.abstractmethod
    async def callback(self, room: nio.MatrixRoom, event: nio.ReactionEvent) -> None:
        pass


class Menu:
    def __init__(
            self,
            timeout: typing.Optional[typing.Union[float, int]] = 600.0,
    ):
        self.timeout = timeout

        self.menu_event_id: typing.Optional[str] = None
        self.menu_room_id: typing.Optional[str] = None

        self.buttons = []
        self.abort = asyncio.Event()

    def _discover_buttons(self):
        for obj in self.__dict__.values():
            if hasattr(obj, "__niobot_menu_button__"):
                button: MenuButton = obj.__niobot_menu_button__
                button.menu = self
                self.add_button(button)

    def add_button(self, button: MenuButton) -> Self:
        if button in self.buttons:
            raise ValueError("Button with the same annotation already exists")

        self.buttons.append(button)
        return self

    def get_button(self, annotation: str) -> typing.Optional[MenuButton]:
        for button in self.buttons:
            if button.annotation == annotation:
                return button
        return None

    def remove_button(self, button: MenuButton) -> Self:
        self.buttons.remove(button)
        return self

    async def check(self, room: nio.MatrixRoom, event: nio.ReactionEvent) -> bool:
        """
        Check if the event is a menu event and if it is, process it.
        By default, this method checks that:

        1. The annotation was on the current menu
        2. There is a button defined for the annotation

        You may want to override this to check authorship, etc.

        :param room: The room where the event happened
        :param event: The event that happened
        :return: True if the event should be processed, False otherwise
        """
        if event.event_id != self.menu_event_id or room.room_id != self.menu_room_id:
            return False

        button = self.get_button(event.key)
        if button is None:
            return False

        return True

    async def start_raw(self, bot: "NioBot", room: nio.MatrixRoom, event: nio.RoomMessage):
        self.menu_event_id = event.event_id
        self.menu_room_id = room.room_id

        for button in self.buttons:
            await bot.add_reaction(room.room_id, event.event_id, button.annotation)

        while self.abort.is_set() is False:
            _r, _e = await bot.wait_for_event(
                nio.ReactionEvent,
                room.room_id,
                check=self.check,
                timeout=self.timeout,
            )

            button = self.get_button(_e.key)
            await button.callback(room, _e)

        self.menu_event_id = None
        self.menu_room_id = None
        self.abort.clear()

    async def start(self, ctx: Context):
        await self.start_raw(ctx.client, ctx.room, ctx.message)


def menu_button(annotation: str):
    # Needs to add the button to the menu
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, room: nio.MatrixRoom, event: nio.ReactionEvent):
            await func(self, room, event)

        wrapper.__niobot_menu_button__ = MenuButton(None, annotation=annotation)
        return wrapper
    return decorator
