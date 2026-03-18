"""Paper summarizer skill – multi-level paper summarization."""


def register():
    """Register paper summarizer tools."""

    def summarize_paper(
        source: str,
        level: str = "standard",
    ) -> dict:
        """Summarize a paper at different levels of detail.

        Parameters
        ----------
        source:
            Path to PDF, ArXiv ID, or URL.
        level:
            Summary level: "brief" (1 paragraph), "standard" (structured),
            "detailed" (section-by-section).

        Returns
        -------
        dict
            Summary with structure depending on level.
        """
        from ..pdf.tools import read_paper

        paper = read_paper(source)
        if "error" in paper:
            return paper

        text = paper.get("text", "")
        metadata = paper.get("metadata", {})

        result = {
            "title": metadata.get("title", ""),
            "page_count": paper.get("page_count", 0),
            "level": level,
        }

        if level == "brief":
            # Just the first ~500 chars as a preview
            result["summary"] = text[:500].strip()
        elif level == "detailed":
            # Include section-level content
            result["full_text"] = text[:20000]
            result["tables"] = paper.get("tables", [])
        else:
            # Standard: first 2000 chars
            result["summary"] = text[:2000].strip()
            result["sections"] = paper.get("sections", {})

        return result

    return {"summarize_paper": summarize_paper}
