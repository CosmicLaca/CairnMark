"""Presentation data for the provider setup workspace."""

from services.model_providers import PROVIDER_SPECS


PROVIDER_ORDER = (
    "llama.cpp",
    "vllm",
    "openrouter",
    "openai",
    "anthropic",
    "mistral",
    "deepseek",
    "opencode",
    "opencode-zen",
    "zai",
    "grok",
    "google",
)

PROVIDER_DESCRIPTIONS = {
    "llama.cpp": (
        "Register models exposed by your local server and choose which catalog "
        "entries remain active."
    ),
    "vllm": (
        "Track the single model currently exposed by the local vLLM "
        "OpenAI-compatible server."
    ),
    "openrouter": (
        "Load the OpenRouter catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "openai": (
        "Load the OpenAI catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "anthropic": (
        "Load the Anthropic catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "mistral": (
        "Load the Mistral catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "deepseek": (
        "Load the DeepSeek catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "opencode": (
        "Load the OpenCode catalog with your API key and choose which hosted "
        "models remain active."
    ),
    "opencode-zen": (
        "Load the OpenCode Zen gateway catalog with your Zen API key and choose "
        "which hosted models remain active."
    ),
    "zai": (
        "Load the Z.ai catalog with your API key and choose which hosted models "
        "remain active."
    ),
    "grok": (
        "Load the Grok catalog with your API key and choose which hosted models "
        "remain active."
    ),
    "google": (
        "Load the Gemini API catalog with your Google AI Studio key and choose "
        "which text-generation models remain active."
    ),
}

PROTOCOL_LABELS = {
    "anthropic": "api.anthropic.com/v1",
    "opencode": "opencode.ai/inference",
}

CATALOG_ROUTES = {
    "opencode": "GET /inference/v1/models",
    "opencode-zen": "GET /zen/v1/models",
    "google": "GET /v1beta/models",
}


def provider_setup_cards(service):
    """Combine provider declarations with saved setup state for the template."""
    providers = []
    custom_providers = [item["provider"] for item in service.custom_providers()]
    for index, provider in enumerate((*PROVIDER_ORDER, *custom_providers), start=1):
        spec = service.spec(provider)
        custom = provider not in PROVIDER_SPECS
        overview = service.saved_provider_overview(provider)
        configuration = overview["configuration"]
        protocol = (
            f"{configuration['ip'].rstrip('/')}:{configuration['port']}"
            if configuration
            else "Setup needed"
        )
        if spec.fixed_endpoint:
            protocol = PROTOCOL_LABELS.get(
                provider,
                spec.fixed_endpoint.removeprefix("https://"),
            )
        kind = "CUSTOM" if custom else ("LOCAL" if spec.local else "ONLINE")
        glyph = "◇" if custom else (
            "⎔" if provider == "llama.cpp" else (
                "◉" if spec.single_live_model else "✦"
            )
        )
        providers.append(
            {
                "name": provider,
                "slug": provider.removesuffix(".cpp").replace(":", "-"),
                "custom": custom,
                "new_custom": False,
                "title": spec.display_name,
                "index": f"{index:02d}",
                "kind": kind,
                "glyph": glyph,
                "description": PROVIDER_DESCRIPTIONS.get(
                    provider,
                    "Use an OpenAI-compatible endpoint and retain the models "
                    "Cairnmark should make available.",
                ),
                "protocol": protocol,
                "summary": overview["summary"],
                "model_name": (
                    "Checking server…" if configuration else "Setup required"
                ),
                "api_provider": spec.requires_api_key,
                "single_model": spec.single_live_model,
                "endpoint": spec.fixed_endpoint or "",
                "default_port": spec.fixed_port or (
                    8001 if provider == "vllm" else 8080
                ),
                "catalog_route": CATALOG_ROUTES.get(provider, "GET /v1/models"),
            }
        )
    return providers


def custom_provider_modal():
    """Return presentation data for the new custom-provider dialog."""
    return {
        "name": "__custom__",
        "slug": "custom-provider",
        "custom": True,
        "new_custom": True,
        "title": "Custom provider",
        "index": "+",
        "kind": "CUSTOM",
        "glyph": "◇",
        "description": "Connect an OpenAI-compatible provider.",
        "protocol": "Setup needed",
        "summary": {"total": 0, "enabled": 0},
        "model_name": "Setup required",
        "api_provider": False,
        "single_model": False,
        "endpoint": "",
        "default_port": 1234,
        "catalog_route": "GET /v1/models",
    }
