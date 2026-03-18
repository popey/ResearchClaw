"""Figure generator skill – create publication-quality figures."""


def register():
    """Register figure generation tools."""
    from .tools import plot_chart

    return {"plot_chart": plot_chart}
