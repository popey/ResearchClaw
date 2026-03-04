"""Citation network skill – explore citation graphs and find related work."""


def register():
    """Register citation network tools."""

    def find_related_papers(
        paper_id: str,
        depth: int = 1,
        max_results: int = 20,
    ) -> dict:
        """Find related papers through citation network exploration.

        Parameters
        ----------
        paper_id:
            Semantic Scholar paper ID, DOI, or ArXiv ID.
        depth:
            Citation graph depth (1 = direct citations, 2 = citations of citations).
        max_results:
            Maximum papers to return.

        Returns
        -------
        dict
            Related papers with citation relationships.
        """
        from ...tools.semantic_scholar import (
            semantic_scholar_citations,
            semantic_scholar_get_paper,
        )

        result = {
            "source_paper": paper_id,
            "citing_papers": [],
            "referenced_papers": [],
        }

        # Get paper info
        paper = semantic_scholar_get_paper(paper_id)
        if "error" in paper:
            return paper

        result["source_title"] = paper.get("title", "")
        result["citing_papers"] = semantic_scholar_citations(paper_id, max_results)
        result["referenced_papers"] = paper.get("references_sample", [])

        return result

    return {"find_related_papers": find_related_papers}
