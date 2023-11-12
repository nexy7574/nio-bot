# Pull from https://github.com/poljar/matrix-nio/pull/451 temporarily.
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union

from nio.responses import ErrorResponse, Response

__all__ = (
    "DirectRoomsErrorResponse",
    "DirectRoomsResponse",
)


class DirectRoomsErrorResponse(ErrorResponse):
    pass


@dataclass
class DirectRoomsResponse(Response):
    """A response containing a list of direct rooms.
    Attributes:
        rooms (List[str]): The rooms joined by the account.
    """

    rooms: Dict[str, List[str]] = field()

    @classmethod
    def from_dict(
        cls,
        parsed_dict: Dict[Any, Any],
    ) -> Union["DirectRoomsResponse", DirectRoomsErrorResponse]:
        if parsed_dict.get("errcode") is not None:
            return DirectRoomsErrorResponse.from_dict(parsed_dict)
        return cls(parsed_dict)
