"""Application persistence initialization."""


def init_storage(app):
    """Normalize database paths and initialize every eager schema."""
    from models.benchmark_metadata import STORE as benchmark_store
    from models.chat_settings import SETTINGS_STORE
    from models.chat_storage import CHAT_STORE
    from models.mcp_settings import STORE as mcp_settings_store
    from models.model_storage import STORE as model_store
    from models.parameter_storage import STORE as parameter_store

    benchmark_store.configure(app)
    model_store.configure(app)
    SETTINGS_STORE.configure(app)
    CHAT_STORE.configure(app, create=False)
    mcp_settings_store.configure(app)
    parameter_store.configure(app, create=False)
