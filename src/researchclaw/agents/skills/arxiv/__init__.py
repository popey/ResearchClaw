"""ArXiv skill – advanced ArXiv search with category monitoring and alerts."""

tools = {}


def register():
    """Register ArXiv skill tools."""
    from .tools import arxiv_download, arxiv_get_paper, arxiv_search

    return {
        "arxiv_search": arxiv_search,
        "arxiv_download": arxiv_download,
        "arxiv_get_paper": arxiv_get_paper,
    }
