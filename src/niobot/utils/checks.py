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


async def _is_creator(ctx: Context) -> (bool, bool):
    """Internal function to check if the sender is the creator of the room."""
    create = await ctx.bot.sync_store.get_room_state_event(ctx.room.room_id, "m.room.create", "")
    if not create:
        raise CheckFailure("No m.room.create event found in room state.")
    is_v12 = create["content"].get("room_version", "1") not in map(str, range(1, 12))

    if is_v12:
        # in v12+, additional_creators exist.
        additional = create["content"].get("additional_creators", [])
        if ctx.event.sender in additional:
            return True, True
    return create["sender"] == ctx.message.sender, is_v12


def sender_has_power(level: int, room_creator_bypass: bool = False):
    """Requires that the sender has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :param room_creator_bypass: If the room creator should bypass the check and always be allowed, regardless of level.
    Irrelevant in v12 rooms.
    :return:
    """

    async def predicate(ctx: Context):
        create = await ctx.bot.sync_store.get_room_state_event(ctx.room.room_id, "m.room.create", "")
        if not create:
            raise CheckFailure("No m.room.create event found in room state.")
        is_creator, is_v12 = await _is_creator(ctx)
        if (room_creator_bypass or is_v12) and is_creator:
            return True
        if (sp := ctx.room.power_levels.get_user_level(ctx.message.sender)) < level:
            raise InsufficientPower(needed=level, have=sp)
        return True

    return check(predicate)


def client_has_power(level: int):
    """Requires that the bot has a certain power level in the current room before running the command.

    :param level: The minimum power level
    :return:
    """

    def predicate(ctx):
        is_creator, is_v12 = _is_creator(ctx)
        if is_v12 and ctx.client.user_id == ctx.message.sender:
            return True
        if (sp := ctx.room.power_levels.get_user_level(ctx.client.user_id)) < level:
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
