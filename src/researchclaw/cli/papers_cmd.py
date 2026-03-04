"""Paper utility commands."""

from __future__ import annotations

import click

from researchclaw.agents.tools.arxiv_search import arxiv_download, arxiv_search


@click.group()
def papers() -> None:
    """Search and manage papers."""


@papers.command("search")
@click.argument("query")
@click.option("--max-results", default=5, type=int)
def search(query: str, max_results: int) -> None:
    result = arxiv_search(query=query, max_results=max_results)
    click.echo(result)


@papers.command("download")
@click.argument("arxiv_id")
@click.option("--save-dir", default="")
def download(arxiv_id: str, save_dir: str) -> None:
    result = arxiv_download(arxiv_id=arxiv_id, output_dir=save_dir)
    click.echo(result)
