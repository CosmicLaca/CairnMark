"""Controller for the prototype's informational pages."""

from pathlib import Path

import markdown
from flask import current_app, render_template
from markupsafe import Markup

from controllers.benchmark_controller import benchmark_controller
from controllers.chat_controller import chat_controller
from controllers.create_benchmark_controller import create_benchmark_controller
from controllers.provider_controller import provider_controller

PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")


def render_readme():
    """Load the project README and convert its Markdown to trusted HTML."""
    try:
        readme_text = README_PATH.read_text(encoding="utf-8")
    except OSError:
        current_app.logger.exception("Could not read %s", README_PATH)
        return Markup("<p>The project README is currently unavailable.</p>")

    # README.md is maintained inside this repository and is trusted content.
    return Markup(
        markdown.markdown(
            readme_text,
            extensions=MARKDOWN_EXTENSIONS,
        )
    )


def get_about_context():
    """Build the additional template context required by the About page."""
    return {"readme_html": render_readme()}


PAGES = (
    {
        "endpoint": "index",
        "path": "/",
        "title": "Home",
        "icon": "⌂",
        "template": "index.html",
        "context_provider": chat_controller.context,
    },
    {
        "endpoint": "create_benchmark",
        "path": "/create_benchmark",
        "title": "Create benchmark JSON",
        "icon": "◇",
        "template": "create_benchmark.html",
        "context_provider": create_benchmark_controller.context,
    },
    {
        "endpoint": "run_benchmark",
        "path": "/run_benchmark",
        "title": "Run benchmark",
        "icon": "▶",
        "template": "run_benchmark.html",
        "context_provider": benchmark_controller.selection_context,
    },
    {
        "endpoint": "evaluate_benchmark",
        "path": "/evaluate_benchmark",
        "title": "Evaluate benchmark",
        "icon": "◎",
        "template": "evaluate_benchmark.html",
        "context_provider": benchmark_controller.evaluate_context,
        "dev_only": True,
    },
    {
        "endpoint": "previous_benchmarks",
        "path": "/previous_benchmarks",
        "title": "Previous benchmarks",
        "icon": "◷",
        "dev_only": True,
    },
    {
        "endpoint": "export_results",
        "path": "/export_results",
        "title": "Export benchmark results",
        "icon": "⇩",
        "dev_only": True,
    },
    {
        "endpoint": "setup_models",
        "path": "/setup_models",
        "title": "Setup models",
        "icon": "⎔",
        "template": "setup_models.html",
        "context_provider": provider_controller.setup_context,
    },
    {
        "endpoint": "about",
        "path": "/about",
        "title": "About",
        "icon": "ⓘ",
        "template": "about.html",
        "context_provider": get_about_context,
    },
)


def available_pages(dev_mode):
    """Return the page catalog entries enabled for the current launch mode.

    Unfinished pages carry ``dev_only`` and stay hidden unless the server was
    started with ``--dev``.
    """
    if dev_mode:
        return PAGES
    return tuple(page for page in PAGES if not page.get("dev_only"))


class IndexController:
    """Render one of the pages declared in :data:`PAGES`."""

    def show(self, page):
        """Render a page-specific template or the shared placeholder."""
        template = page.get("template", "placeholder.html")
        context = {"page": page}
        context_provider = page.get("context_provider")
        if context_provider:
            context.update(context_provider())
        return render_template(template, **context)


index_controller = IndexController()
