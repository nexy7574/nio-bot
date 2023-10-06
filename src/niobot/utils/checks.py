from typing import Optional

from ..commands import check
from ..context import Context
from ..exceptions import CheckFailure, InsufficientPower, NotOwner

__all__ = (
    "is_owner",
    "is_dm",
    "sender_has_power",
    "client_has_power",
)


def is_owner(*extra_owner_ids, name: Optional[str] = None):
    """
    Requires the sender owns the bot ([`NioBot.owner_id`][]), or is in `extra_owner_ids`.
    :param extra_owner_ids: A set of `@localpart:homeserver.tld` strings to check against.
    :param name: The human name of this check.
    :return: True - the check passed.
    :raises NotOwner: The sender is not the owner of the bot and is not in the given IDs.
    """

    def predicate(ctx):
        if ctx.message.sender in extra_owner_ids:
            return True
        if ctx.message.sender != ctx.bot.owner_id:
            raise NotOwner(name)
        return True

    return check(predicate, name)


def is_dm(allow_dual_membership: bool = False, name: Optional[str] = None):
    """
    Requires that the current room is a DM with the sender.

    :param allow_dual_membership: Whether to allow regular rooms, but only with the client and sender as members.
    :param name: The human name of this check.
    :return:
    """

    def predicate(ctx: "Context"):
        if ctx.room.room_id in ctx.client.direct_rooms:
            return True
        if allow_dual_membership:
            members = ctx.room.member_count
            if members == 2 and ctx.client.user_id in ctx.room.users:
                return True
        raise CheckFailure(name)

    return check(predicate, name)


def sender_has_power(level: int, room_creator_bypass: bool = False, name: Optional[str] = None):
    """
    Requires that the sender has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :param room_creator_bypass: If the room creator should bypass the check and always be allowed, regardless of level.
    :param name: The human name of this check
    :return:
    """

    def predicate(ctx):
        if ctx.message.sender == ctx.room.creator and room_creator_bypass:
            return True
        if (sp := ctx.room.power_levels.get(ctx.message.sender, -999)) < level:
            raise InsufficientPower(name, needed=level, have=sp)
        return True

    return check(predicate, name)


def client_has_power(level: int, name: Optional[str] = None):
    """
    Requires that the bot has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :param name: The human name of this check
    :return:
    """

    def predicate(ctx):
        if (sp := ctx.room.power_levels.get(ctx.client.user_id, -999)) < level:
            raise InsufficientPower(name, needed=level, have=sp)
        return True

    return check(predicate, name)
