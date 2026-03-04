"""Literature review skill – generate structured literature reviews."""


def register():
    """Register literature review tools."""

    def generate_review_outline(
        topic: str,
        papers: list[dict] | None = None,
        num_sections: int = 5,
    ) -> dict:
        """Generate a structured literature review outline.

        Parameters
        ----------
        topic:
            Research topic for the review.
        papers:
            Optional list of paper metadata dicts to include.
        num_sections:
            Number of main sections (default 5).

        Returns
        -------
        dict
            Review outline with sections and key points.
        """
        outline = {
            "topic": topic,
            "sections": [
                {
                    "title": "Introduction",
                    "description": f"Overview of {topic} and its significance",
                    "key_points": [
                        "Problem definition",
                        "Scope of the review",
                        "Research questions addressed",
                    ],
                },
                {
                    "title": "Background and Definitions",
                    "description": "Key concepts and terminology",
                    "key_points": [
                        "Core definitions",
                        "Theoretical foundations",
                        "Historical context",
                    ],
                },
                {
                    "title": "Methodology",
                    "description": "Approaches and methods in the literature",
                    "key_points": [
                        "Common methodologies",
                        "Evaluation metrics",
                        "Datasets and benchmarks",
                    ],
                },
                {
                    "title": "Key Findings and Trends",
                    "description": "Major findings and emerging trends",
                    "key_points": [
                        "State-of-the-art results",
                        "Comparative analysis",
                        "Emerging directions",
                    ],
                },
                {
                    "title": "Gaps and Future Directions",
                    "description": "Open problems and opportunities",
                    "key_points": [
                        "Identified gaps",
                        "Limitations of current work",
                        "Promising future directions",
                    ],
                },
            ],
        }

        if papers:
            outline["papers_count"] = len(papers)
            outline["papers_by_year"] = {}
            for p in papers:
                year = str(p.get("year", "unknown"))
                outline["papers_by_year"][year] = (
                    outline["papers_by_year"].get(year, 0) + 1
                )

        return outline

    return {"generate_review_outline": generate_review_outline}
