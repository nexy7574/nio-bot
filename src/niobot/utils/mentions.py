__all__ = ("Mentions",)


class Mentions:
    """
    Controls the mentions of a sent event.

    See: <https://spec.matrix.org/v1.11/client-server-api/#user-and-room-mentions>
    """

    def __init__(self, room: bool, *user_ids: str):
        self.room = room
        """Whether this event mentions the entire room"""
        self.user_ids = list(user_ids)
        """List of user IDs mentioned in the event"""

    def __repr__(self) -> str:
        return f"Mentions({self.room}, *{self.user_ids})"

    def as_body(self) -> dict:
        """Returns the mentions object as a body dict"""
        d = {}
        if self.room:
            d["room"] = True
        if self.user_ids:
            d["user_ids"] = list(set(self.user_ids))  # set() to make all entries unique
        return {"m.mentions": d}

    @classmethod
    def from_body(cls, body: dict) -> "Mentions":
        """Creates a mentions object from a body dict"""
        if "m.mentions" in body:
            body = body["m.mentions"]
        return cls(body.get("room", False), *body.get("user_ids", []))
