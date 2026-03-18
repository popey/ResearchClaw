"""PDF skill – advanced PDF processing and text extraction."""


def register():
    """Register PDF tools."""
    from .tools import read_paper

    return {"read_paper": read_paper}
