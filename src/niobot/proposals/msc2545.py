import typing as t

from pydantic import BaseModel


class PackObject(BaseModel):
    """Represents an image pack"""

    display_name: t.Optional[str] = None
    """
    A display name for the pack.
    Defaults to the room name, if the image pack event is in the room.
    This does not have to be unique from other packs in a room.
    """
    avatar_url: t.Optional[str] = None
    """
    The mxc uri of an avatar/icon to display for the pack.
    Defaults to the room avatar, if the pack is in the room.
    Otherwise, the pack does not have an avatar.
    """
    usage: t.List[t.Literal["emoticon", "sticker"]] = None
    """
    An array of the usages for this pack.
    Possible usages are "emoticon" and "sticker".
    If the usage is absent or empty, a usage for all possible usage types is to be assumed.
    """
    attribution: t.Optional[str] = None
    """The attribution of this pack."""


class ImageObject(BaseModel):
    """Represents an image object from a pack event"""

    url: str
    """The MXC url for this image."""
    body: t.Optional[str] = None
    """
    An optional text body for this image.
    Useful for the sticker body text or the emote alt text.
    Defaults to the shortcode.
    """
    info: t.Optional[t.Dict[str, t.Union[str, int, t.Dict]]] = None
    """
    The already spec'd ImageInfo object used for the info block of m.sticker events.
    """
    usage: t.Optional[t.List[t.Literal["emoticon", "sticker"]]] = None
    """
    An array of the usages for this image.
    The possible values match those of the usage key of a pack object.
    If present and non-empty, this overrides the usage defined at pack level for this particular image.
    This is useful to e.g. have one pack contain mixed emotes and stickers.

    Additionally, as there is only a single account data level image pack,
    this is required to have a mixture of emotes and stickers available in account data.
    """


class ImagePack(BaseModel):
    images: t.Dict[str, ImageObject]
    pack: PackObject
