"""Route registration for the Cairnmark prototype."""

from functools import partial

from flask import current_app, render_template

from controllers.benchmark_controller import benchmark_controller
from controllers.chat_controller import chat_controller
from controllers.create_benchmark_controller import create_benchmark_controller
from controllers.index_controller import (
    PAGES,
    available_pages,
    index_controller,
)
from controllers.provider_controller import provider_controller

RUN_BENCHMARK_PAGE = next(page for page in PAGES if page["endpoint"] == "run_benchmark")
CREATE_BENCHMARK_PAGE = next(
    page for page in PAGES if page["endpoint"] == "create_benchmark"
)

APPLICATION_ROUTES = (
    (
        "/chat/send",
        "chat_send",
        chat_controller.send,
        ("POST",),
    ),
    (
        "/chat/save_settings",
        "chat_save_settings",
        chat_controller.save_settings,
        ("POST",),
    ),
    (
        "/chat/save_attachment_settings",
        "chat_save_attachment_settings",
        chat_controller.save_attachment_settings,
        ("POST",),
    ),
    (
        "/chat/clear",
        "chat_clear",
        chat_controller.clear,
        ("POST",),
    ),
    (
        "/chat/abort",
        "chat_abort",
        chat_controller.abort,
        ("POST",),
    ),
    (
        "/chat/preview/<path:filename>",
        "chat_preview",
        chat_controller.preview,
        ("GET",),
    ),
    (
        "/chat/saved",
        "chat_saved_list",
        chat_controller.list_saved,
        ("GET",),
    ),
    (
        "/chat/save_chat",
        "chat_save_chat",
        chat_controller.save_chat,
        ("POST",),
    ),
    (
        "/chat/load_chat",
        "chat_load_chat",
        chat_controller.load_chat,
        ("POST",),
    ),
    (
        "/chat/delete_chat",
        "chat_delete_chat",
        chat_controller.delete_chat,
        ("POST",),
    ),
    (
        "/chat/saved_system_prompts",
        "chat_saved_system_prompts",
        chat_controller.list_saved_system_prompts,
        ("GET",),
    ),
    (
        "/chat/save_system_prompt",
        "chat_save_system_prompt",
        chat_controller.save_system_prompt,
        ("POST",),
    ),
    (
        "/chat/load_system_prompt",
        "chat_load_system_prompt",
        chat_controller.load_system_prompt,
        ("POST",),
    ),
    (
        "/chat/delete_system_prompt",
        "chat_delete_system_prompt",
        chat_controller.delete_system_prompt,
        ("POST",),
    ),
    (
        "/create_benchmark/category",
        "create_benchmark_category",
        partial(create_benchmark_controller.save_category, page=CREATE_BENCHMARK_PAGE),
        ("POST",),
    ),
    (
        "/create_benchmark/generate",
        "create_benchmark_generate",
        create_benchmark_controller.generate,
        ("POST",),
    ),
    (
        "/run_benchmark/<filename>",
        "run_benchmark_select",
        partial(benchmark_controller.select, page=RUN_BENCHMARK_PAGE),
        ("GET", "POST"),
    ),
    (
        "/run_benchmark/<filename>/content",
        "benchmark_content",
        benchmark_controller.content,
        ("GET",),
    ),
    (
        "/run_benchmark/<filename>/update_response",
        "benchmark_update_response",
        benchmark_controller.update_response,
        ("POST",),
    ),
    (
        "/run_benchmark/<filename>/process_one",
        "benchmark_process_one",
        benchmark_controller.process_one,
        ("POST",),
    ),
    (
        "/run_benchmark/<filename>/save_result",
        "benchmark_save_result",
        benchmark_controller.save_result,
        ("POST",),
    ),
    (
        "/setup_models/fetch_models",
        "fetch_provider_models",
        provider_controller.fetch_models,
        ("GET", "POST"),
    ),
    (
        "/setup_models/save_configuration",
        "save_model_configuration",
        provider_controller.save_configuration,
        ("POST",),
    ),
    (
        "/setup_models/load_configuration",
        "get_saved_model_configuration",
        provider_controller.load_configuration,
        ("GET",),
    ),
    (
        "/setup_models/model_params",
        "get_model_params",
        provider_controller.model_params,
        ("GET",),
    ),
    (
        "/setup_models/model_params/delete",
        "delete_model_params",
        provider_controller.delete_model_params,
        ("POST",),
    ),
    (
        "/setup_models/props_available",
        "get_props_available",
        provider_controller.props_available,
        ("GET",),
    ),
    (
        "/setup_models/provider_status",
        "get_provider_status",
        provider_controller.status,
        ("GET",),
    ),
    (
        "/setup_models/provider_state",
        "update_provider_state",
        provider_controller.update_state,
        ("POST",),
    ),
)


def init_routes(app):
    """Register pages, shared template data, and error handlers."""
    navigation_pages = available_pages(app.config["DEV_MODE"])

    for page in navigation_pages:
        app.add_url_rule(
            page["path"],
            endpoint=page["endpoint"],
            view_func=partial(index_controller.show, page),
        )

    for path, endpoint, view_func, methods in APPLICATION_ROUTES:
        app.add_url_rule(
            path,
            endpoint=endpoint,
            view_func=view_func,
            methods=methods,
        )

    @app.context_processor
    def inject_navigation():
        """Make the launch-mode page catalog available to every template."""
        return {"navigation": navigation_pages}

    @app.errorhandler(404)
    def not_found_error(_error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        current_app.logger.error(
            "Unhandled application error",
            exc_info=(type(error), error, error.__traceback__),
        )
        return render_template("500.html"), 500
