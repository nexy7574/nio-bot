from .utils import *
from .client import *
from .attachment import *
from .commands import *
from .context import *
from .exceptions import *

try:
    import __version__
    from .__version__ import *
except ImportError:
    __version__ = "0.0.0"
    __version_tuple__ = (0, 0, "dev0", "gFFFFFF")


__author__ = "Nexus <pip@nexy7574.co.uk>"
__license__ = "GNU GPLv3"
__url__ = "https://github.com/EEKIM10/niobot"
__title__ = "niobot"
__description__ = "A Matrix bot framework written in Python built on matrix-nio."
