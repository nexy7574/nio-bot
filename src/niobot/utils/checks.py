import urllib.parse

from ..commands import check
from ..context import Context
from ..exceptions import CheckFailure, InsufficientPower, NotOwner

__all__ = (
    "client_has_power",
    "from_homeserver",
    "is_dm",
    "is_owner",
    "sender_has_power",
)


def is_owner(*extra_owner_ids):
    """Requires the sender owns the bot (`[NioBot.owner_id][]`), or is in `extra_owner_ids`.
    :param extra_owner_ids: A set of `@localpart:homeserver.tld` strings to check against.
    :return: True - the check passed.
    :raises NotOwner: The sender is not the owner of the bot and is not in the given IDs.
    """

    def predicate(ctx):
        if ctx.message.sender in extra_owner_ids:
            return True
        if ctx.message.sender != ctx.bot.owner_id:
            raise NotOwner()
        return True

    return check(
        predicate,
    )


def is_dm(allow_dual_membership: bool = False):
    """Requires that the current room is a DM with the sender.

    :param allow_dual_membership: Whether to allow regular rooms, but only with the client and sender as members.
    :return:
    """

    def predicate(ctx: "Context"):
        if ctx.room.room_id in ctx.client.direct_rooms:
            return True
        if allow_dual_membership:
            members = ctx.room.member_count
            if members == 2 and ctx.client.user_id in ctx.room.users:
                return True
        raise CheckFailure()

    return check(predicate)


def sender_has_power(level: int, room_creator_bypass: bool = False):
    """Requires that the sender has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :param room_creator_bypass: If the room creator should bypass the check and always be allowed, regardless of level.
    :return:
    """

    def predicate(ctx):
        if ctx.message.sender == ctx.room.creator and room_creator_bypass:
            return True
        if (sp := ctx.room.power_levels.get(ctx.message.sender, -999)) < level:
            raise InsufficientPower(needed=level, have=sp)
        return True

    return check(predicate)


def client_has_power(level: int):
    """Requires that the bot has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :return:
    """

    def predicate(ctx):
        if (sp := ctx.room.power_levels.get(ctx.client.user_id, -999)) < level:
            raise InsufficientPower(needed=level, have=sp)
        return True

    return check(predicate)


def from_homeserver(*homeservers: str):
    """Requires that the sender is from one of the given homeservers.

    :param homeservers: The homeservers to allowlist.
    :return:
    """
    parsed_hs = set()
    for raw_hs in homeservers:
        if raw_hs.startswith("http"):
            _parsed = urllib.parse.urlparse(raw_hs)
            if not _parsed.netloc:
                raise ValueError(f"Invalid homeserver URL: {raw_hs}")
            parsed_hs.add(_parsed.netloc)
        else:
            parsed_hs.add(raw_hs)

    def predicate(ctx: Context):
        hs = ctx.message.sender.split(":")[-1]
        return hs in homeservers

    return check(predicate)
