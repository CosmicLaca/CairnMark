# MCP tool and local SearXNG setup

This guide explains how to configure a local SearXNG instance and connect it to
CairnMark through either llama.cpp-managed or Custom MCP tools. Both sides must
be configured correctly: SearXNG controls which search engines actually run,
while CairnMark controls which service, subtools, and request defaults the model
may use.

Keep all services bound to localhost. This setup is intended for CairnMark's
single-user local environment, not for a public SearXNG deployment.

## 1. Configure local SearXNG

Edit the `settings.yml` used by the running SearXNG process. This is not always
the file in the downloaded source or installer directory. Check the launcher or
the `SEARXNG_SETTINGS_PATH` environment variable to find the active file, then
restart SearXNG after every change.

The following is a practical local starting point:

```yaml
use_default_settings:
  engines:
    keep_only:
      - bing
      - yahoo
      - mwmbl
      - wikipedia
      - github
      - stackoverflow

general:
  debug: false
  instance_name: "Local SearXNG"

server:
  bind_address: "127.0.0.1"
  port: 8888
  secret_key: "GENERATE_A_RANDOM_SECRET"
  limiter: false
  public_instance: false
  image_proxy: false

search:
  safe_search: 0
  default_lang: "all"
  formats:
    - html
    - json
    - csv
    - rss

outgoing:
  request_timeout: 10.0
  max_request_timeout: 20.0
  pool_connections: 100
  pool_maxsize: 20
  enable_http2: true

engines:
  - name: bing
    disabled: false
  - name: yahoo
    disabled: false
  - name: mwmbl
    disabled: false
  - name: wikipedia
    disabled: false
  - name: github
    disabled: false
  - name: stackoverflow
    disabled: false
```

Generate a unique secret instead of copying the placeholder. For example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The engine list is a conservative starting point, not a permanent universal
list. Public engines can change behavior, reject automated traffic, apply
regional restrictions, or temporarily suspend requests. Do not enable every
engine blindly. Start with a small working set and adjust it after testing.

`safe_search: 0` means unrestricted/off, `1` means moderate, and `2` means
strict. Disabling the limiter is appropriate only for a private localhost
instance.

## 2. Verify SearXNG before configuring CairnMark

First check that the JSON API is reachable and returns results independently of
CairnMark:

```powershell
Invoke-RestMethod "http://127.0.0.1:8888/config"
$query = [uri]::EscapeDataString("who is the current singer of Axel Rudi Pell")
Invoke-RestMethod "http://127.0.0.1:8888/search?q=$query&format=json&categories=general"
```

The search response should contain a non-empty `results` list. Also inspect
`unresponsive_engines`: an engine listed there may be blocked, rate-limited, or
temporarily suspended. Fix the local SearXNG configuration before debugging the
chat or model when the direct API request also has no results.

## 3. Understand the two CairnMark connection types

CairnMark can show the same MCP service through two independent providers:

- **llama.cpp** tools are discovered from the active llama.cpp provider. The
  llama.cpp server must already have been started with its MCP configuration,
  such as `--mcp-servers-config <path-to-mcp.json>`.
- **Custom** tools are declared in `services/mcv.json` and are started or
  contacted by CairnMark.

The two entries can coexist and have separate saved settings. The main-page
tooltip identifies them as `[provider]::[service]`, for example
`llama.cpp::searxng` and `custom::searxng`. Change the entry that corresponds to
the provider you intend to use.

## 4. Recommended CairnMark SearXNG settings

Open the chat page, select the tool icon, and configure the relevant SearXNG
service in **MCP settings**:

1. Set **Endpoint address and port** to `http://127.0.0.1:8888`.
2. Select **Test access** and confirm the endpoint is online.
3. Use page `1` for ordinary searches.
4. Use **Any time** unless the question requires a date range.
5. Set SafeSearch to `0` for unrestricted/off, if appropriate for your use.
6. Leave the engine selection empty initially. An empty selection lets SearXNG
   use the engines enabled by its active configuration. Select engines only
   after confirming their exact names and availability.
7. Enable the main service switch and only the subtools the model needs, such
   as `search`. Save the modal.
8. Right-click the main-page tool icon and enable global tool use. The icon
   remains clickable even when tool execution is globally disabled.

When a setup field supports multiple values, CairnMark sends the selected
values as a list. Selecting several engines does not install or activate those
engines on SearXNG; it only restricts a request to names already available on
the server.

Use **Status check** to repeat endpoint checks without rediscovering every MCP
tool. Use **Refresh** when services or subtools have been added, removed, or
renamed; it refreshes the cached Custom tool metadata in `instance/tools.db`.

## 5. Test tool use in chat

After saving the setup, try:

> Use the SearXNG search tool to find the current singer of Axel Rudi Pell.
> Include the result URLs.

During execution, the assistant bubble identifies the provider, tool, and
tool-call round. Successful URLs in the final response are rendered as links.

## Troubleshooting

### Direct SearXNG requests return no results

The problem is outside CairnMark. Check `unresponsive_engines`, remove blocked
engines, verify the active `settings.yml`, and restart SearXNG. Search engines
may return HTTP 403/429 responses or become suspended after an earlier
successful request.

### Direct requests work, but CairnMark returns no results

- Confirm that the correct provider entry is enabled: `llama.cpp::searxng` and
  `custom::searxng` have independent settings.
- Clear the selected engine list and save, so the server can use its enabled
  defaults.
- Confirm the `search` subtool and its parent service switch are enabled.
- Confirm global tool use is enabled from the tool icon's right-click dialog.
- Run **Status check**, then use **Refresh** if the service definition or its
  exposed tools changed.

### An engine appears in the setup list but does not work

The setup schema can offer a name that the running SearXNG instance does not
currently expose or permit. The running server is authoritative. Check its
`/config` response or the MCP service's engine-list tool, then update the
selection or SearXNG configuration.

### Format expectations

SearXNG commonly exposes `json`, `csv`, and `rss` as machine-readable response
formats, in addition to its HTML interface. An MCP server may transform a
result into Markdown for the model and may accept only the fields declared by
its own tool schema. CairnMark forwards supported saved defaults; it does not
force an unsupported format argument into a tool call.
