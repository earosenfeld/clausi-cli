"""Clausi - AI compliance auditing CLI."""

__version__ = "1.0.2"
__author__ = "Clausi"
__email__ = "support@clausi.ai"

__all__ = ["cli", "main", "__version__"]


def __getattr__(name):
    """Keep package metadata imports lightweight; load the CLI on demand."""
    if name in {"cli", "main"}:
        from clausi.cli import cli, main
        return {"cli": cli, "main": main}[name]
    raise AttributeError(name)
