""" Top-level package for polyphasia. """

from importlib import metadata

__metadata__ = metadata.metadata(__name__)
__author__ = __metadata__.get("Author", "")
__version__ = __metadata__.get("Version", "")
