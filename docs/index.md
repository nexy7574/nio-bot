# Index
## Welcome to the Nio-Bot Documentation

!!! warning
    This documentation is still a work in progress, and is auto-generated from docstrings.
    If you notice any errors, please [open a new issue](https://github.com/EEKIM10/niobot/issues/new).

    Furthermore, the docs are still partially written in sphinx (RST) format. Broken links are to be expected.

-------------

## Installing
As this package is not yet on PyPi, you must install from git:

### Via pip:
```bash
$ pip install git+https://github.com/EEKIM10/niobot.git
```

### In requirements.txt:
```txt
niobot[e2ee,cli] @ git+https://github.com/EEKIM10/niobot.giit
```

## CLI
The `niobot` package comes with a CLI tool, which can be used to create templates, get access tokens, resolve
homeservers, and more (in the future).

You can install the cli tool with the `cli` extra. The command itself is `niocli`.

## Version information
Version information is found in the `__version__.py` file, which is created while installing the package.

```python
from niobot.__version__ import __version__
print(__version__)
```

## Logging
Logging is done using the `logging` module. The logger is named `niobot.<module>`. For example:

```python
import logging
import niobot

logging.basicConfig(level=logging.INFO)
bot = niobot.NioBot(...)

bot.run(...)
```
This will now output a bunch of logs to your console, which you can use to debug your bot.
