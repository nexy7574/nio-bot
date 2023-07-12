from nio import *
from . import utils
from .utils import *
from .client import *
from .commands import *
from .context import *
from .exceptions import *
try:
    from .attachment import *
    ATTACHMENTS_AVAILABLE = True
except ImportError:
    pass
    ATTACHMENTS_AVAILABLE = False

try:
    import __version__ as version_meta
except ImportError:
    class __VersionMeta:
        __version__ = "0.0.dev0+gFFFFFF"
        __version_tuple__ = (0, 0, "dev0", "gFFFFFF")
    version_meta = __VersionMeta()

__author__ = "Nexus <pip@nexy7574.co.uk>"
__license__ = "GNU GPLv3"
__url__ = "https://github.com/EEKIM10/niobot"
__title__ = "niobot"
__description__ = "A Matrix bot framework written in Python built on matrix-nio."
__user_agent__ = f"Mozilla/5.0 {__title__}/{version_meta.__version__} ({__url__})"
