"""Tools for reading and analyzing FLIR ATS thermal video files."""

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version

try:
    __version__ = version("flir-ats-tools")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
