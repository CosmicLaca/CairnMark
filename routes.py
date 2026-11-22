"""Route registration for the Cairnmark prototype."""

from functools import partial

from flask import current_app, render_template

from controllers.benchmark_controller import benchmark_controller
from controllers.chat_controller import chat_controller
from controllers.create_benchmark_controller import create_benchmark_controller
from controllers.index_controller import (
    PAGES,
    TOOL_SETUP_PATH,
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
        "/tool-setup.md",
        "tool_setup_manual",
        partial(index_controller.markdown_manual, TOOL_SETUP_PATH),
        ("GET",),
    ),
    (
        "/manual/<path:filename>",
        "manual_asset",
        index_controller.manual_asset,
        ("GET",),
    ),
    (
        "/chat/send",
        "chat_send",
        chat_controller.send,
        ("POST",),
    ),
    (
        "/chat/compact",
        "chat_compact",
        chat_controller.compact,
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
        "/chat/save_compact_settings",
        "chat_save_compact_settings",
        chat_controller.save_compact_settings,
        ("POST",),
    ),
    (
        "/chat/save_seed_settings",
        "chat_save_seed_settings",
        chat_controller.save_seed_settings,
        ("POST",),
    ),
    (
        "/chat/save_seed_switch",
        "chat_save_seed_switch",
        chat_controller.save_seed_settings,
        ("POST",),
    ),
    (
        "/chat/save_history_settings",
        "chat_save_history_settings",
        chat_controller.save_history_settings,
        ("POST",),
    ),
    (
        "/chat/save_history_switch",
        "chat_save_history_switch",
        chat_controller.save_history_settings,
        ("POST",),
    ),
    (
        "/chat/save_send_all_previous",
        "chat_save_send_all_previous",
        chat_controller.save_history_settings,
        ("POST",),
    ),
    (
        "/chat/save_randomize_seed",
        "chat_save_randomize_seed",
        chat_controller.save_seed_settings,
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
        "/chat/mineru_available",
        "chat_mineru_available",
        chat_controller.mineru_available,
        ("GET",),
    ),
    (
        "/chat/process_document",
        "chat_process_document",
        chat_controller.process_document,
        ("POST",),
    ),
    (
        "/chat/mineru_settings",
        "chat_mineru_settings",
        chat_controller.mineru_settings_get,
        ("GET",),
    ),
    (
        "/chat/save_mineru_settings",
        "chat_save_mineru_settings",
        chat_controller.save_mineru_settings,
        ("POST",),
    ),
    (
        "/chat/preview/<path:filename>",
        "chat_preview",
        chat_controller.preview,
        ("GET",),
    ),
    (
        "/chat/external_image_download",
        "chat_external_image_download",
        chat_controller.download_external_image,
        ("GET",),
    ),
    (
        "/chat/saved",
        "chat_saved_list",
        partial(chat_controller.saved_chat, "list"),
        ("GET",),
    ),
    (
        "/chat/save_chat",
        "chat_save_chat",
        partial(chat_controller.saved_chat, "save"),
        ("POST",),
    ),
    (
        "/chat/load_chat",
        "chat_load_chat",
        partial(chat_controller.saved_chat, "load"),
        ("POST",),
    ),
    (
        "/chat/export",
        "chat_export",
        chat_controller.export_chat,
        ("POST",),
    ),
    (
        "/chat/import",
        "chat_import",
        chat_controller.import_chat,
        ("POST",),
    ),
    (
        "/chat/replace_chat",
        "chat_replace_chat",
        partial(chat_controller.saved_chat, "replace"),
        ("POST",),
    ),
    (
        "/chat/delete_chat",
        "chat_delete_chat",
        partial(chat_controller.saved_chat, "delete"),
        ("POST",),
    ),
    (
        "/chat/saved_system_prompts",
        "chat_saved_system_prompts",
        partial(chat_controller.saved_system_prompt, "list"),
        ("GET",),
    ),
    (
        "/chat/save_system_prompt",
        "chat_save_system_prompt",
        partial(chat_controller.saved_system_prompt, "save"),
        ("POST",),
    ),
    (
        "/chat/load_system_prompt",
        "chat_load_system_prompt",
        partial(chat_controller.saved_system_prompt, "load"),
        ("POST",),
    ),
    (
        "/chat/delete_system_prompt",
        "chat_delete_system_prompt",
        partial(chat_controller.saved_system_prompt, "delete"),
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
        "/chat/mcp_configuration",
        "chat_mcp_configuration",
        chat_controller.mcp_configuration,
        ("GET",),
    ),
    (
        "/chat/mcp_configuration/import_opencode",
        "chat_import_opencode_mcp",
        chat_controller.import_opencode_mcp,
        ("POST",),
    ),
    (
        "/chat/mcp_configuration/server",
        "chat_save_mcp_server",
        chat_controller.save_mcp_server,
        ("POST",),
    ),
    (
        "/chat/mcp_settings",
        "chat_mcp_settings_get",
        chat_controller.mcp_settings_get,
        ("GET",),
    ),
    (
        "/chat/mcp_settings/save",
        "chat_mcp_settings_save",
        chat_controller.mcp_settings_save,
        ("POST",),
    ),
    (
        "/chat/mcp_global_state",
        "chat_mcp_global_state",
        chat_controller.mcp_global_state,
        ("GET", "POST"),
    ),
    (
        "/chat/mcp_tools/refresh",
        "chat_mcp_tools_refresh",
        chat_controller.mcp_tools_refresh,
        ("POST",),
    ),
    (
        "/chat/mcp_status",
        "chat_mcp_status",
        chat_controller.mcp_status,
        ("GET",),
    ),
    (
        "/chat/mcp_endpoint_test",
        "chat_mcp_endpoint_test",
        chat_controller.mcp_endpoint_test,
        ("POST",),
    ),
    (
        "/chat/llama_managed_tools",
        "chat_llama_managed_tools",
        chat_controller.llama_managed_tools,
        ("GET",),
    ),
    (
        "/chat/llama_managed_mcp_status",
        "chat_llama_managed_mcp_status",
        chat_controller.llama_managed_mcp_status,
        ("GET",),
    ),
    (
        "/setup_models/model_params/status",
        "get_model_params_status",
        provider_controller.model_params_status,
        ("GET",),
    ),
    (
        "/setup_models/model_params/delete",
        "delete_model_params",
        provider_controller.delete_model_params,
        ("POST",),
    ),
    (
        "/setup_models/model_params/save",
        "save_model_params",
        provider_controller.save_model_params,
        ("POST",),
    ),
    (
        "/setup_models/props_available",
        "get_props_available",
        provider_controller.props_available,
        ("GET",),
    ),
    (
        "/setup_models/ctx_mode",
        "get_ctx_mode",
        provider_controller.ctx_mode,
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
    (
        "/setup_models/provider_selection",
        "save_provider_selection",
        provider_controller.save_selection,
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
