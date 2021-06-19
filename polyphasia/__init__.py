""" Top-level package for polyphasia. """
import importlib_metadata as metadata

from .logger import logger

__metadata__ = metadata.metadata(__name__)
__author__ = __metadata__["Author"]
__version__ = __metadata__["Version"]

# Disable logging by default.
logger.disable("polyphasia")
