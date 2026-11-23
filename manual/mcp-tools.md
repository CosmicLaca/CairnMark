# MCP tool handling

CairnMark can expose enabled MCP tools to compatible chat models. Tool access is
off on first run and is controlled at three levels: the global switch, the main
service switch, and individual subtool switches.

<!-- Screenshot placeholder: add manual/mcp-settings.jpg after capturing the MCP settings modal. -->

---

| Main tool setup                                                                             | Tool setup                                                                                | Endpoint setting                                                                          |
|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| <img src="./tool-setting-01.jpg" height="300px" alt="MCP tool setting"> | <img src="./tool-setting-02.jpg" height="300px" alt="MCP tool setting"> | <img src="./tool-setting-03.jpg" height="300px" alt="MCP tool setting"> |
 
---

## Connection sources

| Source | Ownership | Discovery |
| --- | --- | --- |
| llama.cpp | The active llama.cpp server | The server must start with its own MCP configuration |
| Custom | CairnMark | Declarations live in `services/mcp.json` and use stdio or streamable HTTP |

The same service can exist through both sources. CairnMark displays qualified
names such as `llama::searxng` and `custom::searxng` so their saved settings do
not collide.

---

## First setup

1. Select the tool button on Home to open **MCP settings**.
2. If no Custom configuration exists, create one or explicitly import usable
   MCP declarations from OpenCode.
3. Expand a reachable service.
4. Enable its main switch and only the required subtools.
5. Fill any service-specific setup fields.
6. Select **Save**.
7. Right-click the tool button, enable global tool use, and save again.

Import from OpenCode is offered only on first setup and is never automatic.
Private connection declarations remain in `services/mcp.json` rather than the
main application database.

---

## Service-specific setup forms

Optional schemas named `static/tool-setup-[service].json` define setup controls
for a service. CairnMark supports text, password, integer, list, and endpoint
fields. Current endpoint schemas include SearXNG, PostgreSQL, and ComfyUI.

Every field declared as `type: password` is encrypted in `instance/tools.db`
using the Fernet key in `.secret/`. Password values are decrypted only for
backend service calls and are not returned to browser JavaScript.

---

## Save, status check, and refresh

- **Save** stores settings and switch states for services that were reachable
  during the current modal session.
- **Status check** repeats reachability checks without changing cached tool
  definitions or saved switches.
- **Refresh** rediscovers Custom subtools and replaces that service's cached
  definitions in `instance/tools.db`.
- **Cancel** closes the modal without persisting edited fields.

<img src="./tool-setup.jpg" height="400px" alt="MCP tool global setting">

Use **Status check** for availability problems. Use **Refresh** only after a
service adds, removes, or renames tools.

---

## Global tool status and execution policy

Right-click the tool icon below the chat input to open **Tool status**. These
settings apply to every MCP source and are saved in `instance/tools.db` when
**Save** is selected:

| Setting | Default | Purpose |
| --- | ---: | --- |
| Enable/Disable tools | Off | Pauses or permits all saved tool services without changing their individual switches |
| Maximum tool-call rounds | 15 | Limits model-to-tool continuation rounds per response; range 1–20 |
| Maximum total tool calls | 30 | Limits all calls in one response, including parallel calls; range 1–100 |
| Stop after consecutive failures | 2 | Ends tool execution after repeated failures; range 1–10 |
| Maximum result characters | 20,000 | Truncates each tool result before returning it to the model; range 1,000–500,000 |
| Tool-use policy | Automatic | Controls when enabled definitions may be sent to the model |
| Add tool guidance to system prompt | On | Appends runtime-only instructions and the enabled tool names |
| Tool guidance template | Built in | Customizes the runtime guidance; `{tools}` is replaced with qualified tool names |
| Capture webpage preview | On | Creates hover screenshots for ordinary public page links in assistant responses |
| Webpage preview timeout | 2 seconds | Bounds each page capture; range 1–30 seconds |

<img src="./tool-global.jpg" height="550px" alt="MCP tool global setting">

The global switch does not rewrite service or subtool choices. Turning it off
temporarily pauses them; turning it on restores the previously selected set.

The tool-use policies behave as follows:

- **Automatic** lets the model choose enabled tools when useful.
- **Ask before each response** prompts for permission before sending enabled
  tools with that request.
- **Manual only** exposes tools only when the user message starts with `/tool`
  or `/tools`.

Tool guidance is appended to the outgoing system prompt only at request time;
it does not overwrite the visible or saved system prompt. If a custom template
omits `{tools}`, CairnMark appends the available-tool list automatically.

---

## Tool execution

When all three switch levels are enabled, CairnMark sends only those enabled
definitions to the model. The model selects a tool, CairnMark validates and
executes it, appends the result to the model transcript, and asks the model to
continue. Same-named tools from different sources receive distinct internal
aliases.

Execution stops at the configured round, total-call, or consecutive-failure
limit. CairnMark then removes tool definitions and asks the model for a final
response. During execution the loading bubble shows
`provider::tool call... [n]`; after tool work it returns to the normal thinking
state.

The completed assistant bubble displays a tool icon next to **Show API request
body** when at least one tool was called. Its tooltip lists each distinct
`provider::tool` identity used by that response. This audit marker is stored
with active history, saved chats, and exported conversations.

Custom stdio services remain connected for the complete assistant tool loop.
This allows stateful servers such as LibreOffice to create a document, reuse its
document ID across editing calls, save it, and close it before the MCP process
ends.

Successful LibreOffice saves inside `Generated-documents` render a document
card and download action. CairnMark restores the card when loading active
history, resuming a saved conversation, or importing a chat, provided the file
still exists locally. Existing save-as targets receive a timestamped filename
instead of being overwritten.

---

## SearXNG

For local SearXNG installation, engine configuration, direct API checks, image,
audio, and video search examples, and troubleshooting, follow the complete
**[MCP tool and local SearXNG setup guide](./tool-setup.md)**.

## Custom tool examples

For detailed app-level installation, form values, test prompts, output handling,
and troubleshooting for the included Weather and Stock examples, AntV Chart,
and LibreOffice, follow **[Custom MCP tool examples](./mcp-tools-examples.md)**.

---


| Search radio station (player on the result)                             | Search actual information                                               |
|-------------------------------------------------------------------------|-------------------------------------------------------------------------|
| <img src="./tool-example-01.jpg" height="400px" alt="MCP tool example"> | <img src="./tool-example-02.jpg" height="400px" alt="MCP tool example"> |


| Read content from local and from web                                    | Summarize info by web search                                            |
|-------------------------------------------------------------------------|-------------------------------------------------------------------------|
| <img src="./tool-example-03.jpg" height="400px" alt="MCP tool example"> | <img src="./tool-example-04.jpg" height="400px" alt="MCP tool example"> |
## Troubleshooting

### The tool button is absent

The active model does not report tool-call capability in its saved model
parameters. Reopen the local parameter modal to refresh capabilities, or select
a capable model.

### A service is offline

- Verify its command, arguments, URL, and timeout in `services/mcp.json`.
- For an endpoint schema, check unsaved values with **Test access**.
- For llama.cpp tools, confirm the server started with the intended MCP config.
- Use **Status check** after correcting the endpoint.

### A tool is visible but never called

Confirm the global, service, and subtool switches are all enabled. Ask the model
explicitly to use that tool and require returned source URLs or tool-derived
facts rather than simulated examples.
