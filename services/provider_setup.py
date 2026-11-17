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
    for index, provider in enumerate(PROVIDER_ORDER, start=1):
        spec = PROVIDER_SPECS[provider]
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
        providers.append(
            {
                "name": provider,
                "slug": provider.removesuffix(".cpp"),
                "title": spec.display_name,
                "index": f"{index:02d}",
                "kind": "LOCAL" if spec.local else "ONLINE",
                "glyph": "⎔" if provider == "llama.cpp" else (
                    "◉" if spec.single_live_model else "✦"
                ),
                "description": PROVIDER_DESCRIPTIONS[provider],
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
