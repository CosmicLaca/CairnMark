"""Category rules shared by benchmark organization and creation."""

from models.benchmark_metadata import BENCHMARK_METADATA

UNCATEGORIZED = "Uncategorized"
MAX_CATEGORY_LENGTH = 80


def category_names():
    """Return saved categories, including collections without files."""
    return BENCHMARK_METADATA.categories()


def normalize_new_category(value, categories):
    """Return a canonical category name and a validation error, if any."""
    category = " ".join(value.split())
    if not category:
        return None, "Enter a name for the new category."
    if len(category) > MAX_CATEGORY_LENGTH:
        return None, "Category names must be 80 characters or fewer."
    matching_category = next(
        (
            saved_category
            for saved_category in categories
            if saved_category.casefold() == category.casefold()
        ),
        None,
    )
    return matching_category or category, None


def create_category(name):
    """Persist one category for later benchmark metadata."""
    return BENCHMARK_METADATA.category(name)
