# ComfyUI MCP settings and usage

This guide connects CairnMark to an existing ComfyUI installation through the
`comfyui-mcp` service. It does not cover installing ComfyUI, models, custom
nodes, or the MCP package. Complete those steps before configuring CairnMark.

ComfyUI should expose its local API, normally at
`http://127.0.0.1:8188`. CairnMark uses that endpoint for health checks,
generation tracking, and image retrieval.

> **Local access:** Keep a local ComfyUI endpoint bound to localhost unless you
> intentionally configured authentication and secure remote access. A remote
> endpoint receives prompts, workflows, uploaded inputs, and generated media.

## Application-level service settings

Open **Home → MCP settings**, select the `comfyui` service, and verify its
application-level values:

| Field | Value |
| --- | --- |
| Name | `comfyui` |
| Type | Local MCP service |
| Command | The existing command that starts `comfyui-mcp`, commonly `npx` |
| Args | The existing arguments for `comfyui-mcp`, commonly `["-y","comfyui-mcp"]` |
| Timeout (ms) | `10000` is sufficient for ordinary MCP calls |

The ComfyUI setup panel contains these fields:

| Setup field | Example | Purpose |
| --- | --- | --- |
| ComfyUI API endpoint | `http://127.0.0.1:8188` | API used for health, queue, history, and media requests |
| API start command | `H:/Comfy_P313_CU130/start.bat` | Optional command used when the API is offline at tool-call time |
| API stop command | Empty | Optional stop script; an empty field is valid |
| Test access | Select the button | Checks `<endpoint>/system_stats` without generating media |

Use an absolute path for a start or stop command. Forward slashes and Windows
backslashes are both accepted in the saved setup field.

The MCP timeout and image-generation wait are separate. `comfyui-mcp` normally
returns a prompt ID quickly, so a 10-second MCP timeout is sufficient.
CairnMark then waits for the submitted ComfyUI prompt for up to 300 seconds,
reads its output from `/history`, and downloads the image through `/view`.

## Automatic start and stop

The start and stop commands are optional. CairnMark checks the endpoint when an
enabled ComfyUI tool is actually called:

1. If the endpoint is already online, CairnMark assumes ComfyUI was started
   externally. It does not run the start command, does not claim ownership of
   that process, and does not stop it later.
2. If the endpoint is offline and an API start command is saved, CairnMark
   starts it without opening another terminal window and displays
   **Starting ComfyUI...** in the assistant activity label.
3. CairnMark waits for `/system_stats` before making the MCP tool call.
4. Only a process launched by the current CairnMark process is eligible for
   automatic shutdown.
5. If an API stop command is saved, CairnMark runs it before terminating its
   owned process tree. If the stop field is empty, it terminates only the
   process tree it launched.

In the automatic-tool-scope quick menu, an offline service with a configured
start command remains selectable and uses the auto-start visual state. An
offline service without a start command is unavailable until its endpoint is
reachable.

## Choosing ComfyUI subtools

`comfyui-mcp` exposes many tools. Do not enable all of them for ordinary image
generation. Every enabled schema consumes model context and gives the model
more possible actions to choose from.

Recommended small profiles:

| Goal | Enable these subtools | Notes |
| --- | --- | --- |
| Generate with a known checkpoint | `generate_image` | Smallest and recommended profile; CairnMark waits and attaches the result automatically |
| Discover installed checkpoints | `list_local_models` | Enable temporarily, then disable after copying the exact filename |
| Manually inspect a job or older image | `queue`, `get_image` | Not required for normal CairnMark-managed generation |
| Save generation defaults | `get_defaults` | Enable temporarily to read or persist checkpoint and sampling defaults |
| Build and run an API workflow | `create_workflow`, `enqueue_workflow` | Advanced graph control instead of the high-level generator |
| Use an existing workflow | `get_workflow`, `enqueue_workflow` | Loads a workflow and submits its API-format graph |
| Store a generated workflow | `save_workflow` | Writes to the ComfyUI user workflow library and may overwrite the same filename |
| Image-to-image or reference input | `upload_image`, `generate_image` | Upload the input first, then reference its ComfyUI filename |
| Inspect installed model files | `list_local_models`, `model_metadata` | Metadata inspection is more expensive; keep the candidate list small |

Enable destructive or administrative tools such as model removal, queue
clearing, restart, custom-node installation, and manifest application only for
the request that needs them. Review the exact arguments before allowing the
call.

When **Automatic tool scope** is enabled, use the quick accordion under the
chat input to select only the current profile. The red LED means a subtool is
included; the grey LED means it is excluded. The current quick selection is
saved to `instance/tools.db` when the message is sent, not when an LED is
clicked, and is restored after reloading the page.

## Basic text-to-image tests

For these prompts, enable only `generate_image`.

SD 1.x test with an exact checkpoint:

> Generate one 512×512 image using ComfyUI. Use checkpoint
> `BestAll\photoart_V30.safetensors`, 15 steps, CFG 6, Euler sampler, normal
> scheduler, and seed 12345. Prompt: “a small stone lighthouse on a moonlit
> coast, cinematic photograph.” Wait for completion and display the resulting
> image.

Different-seed test:

> Generate one 512×512 image using ComfyUI. Use checkpoint
> `BestAll\photoart_V30.safetensors`, 15 steps, CFG 6, Euler sampler, normal
> scheduler, and seed 54321. Prompt: “a small stone lighthouse on a stormy
> coast at sunset, cinematic photograph.” Wait for completion and display the
> resulting image.

SDXL test, replacing the placeholder with an exact installed filename:

> Generate one 1024×1024 image using ComfyUI. Use checkpoint
> `[EXACT_SDXL_CHECKPOINT]`, 20 steps, CFG 6, Euler sampler, normal scheduler,
> and seed 24680. Prompt: “an observatory above a sea of clouds at sunrise,
> cinematic architectural photograph.” Wait for completion and display the
> resulting image.

An explicit seed makes a generation reproducible. Submitting the same graph,
prompt, checkpoint, and seed again allows ComfyUI to reuse its cached nodes. A
terminal execution time near `0.01 seconds` can therefore be a successful
cached result rather than an error. Change the seed when testing a fresh run.

## Listing models without flooding the response

Temporarily enable only `list_local_models`.

SDXL candidates:

> Use ComfyUI `list_local_models` to inspect checkpoints only. Find filenames
> that appear to be SDXL models. Return at most 10 exact checkpoint filenames,
> sorted alphabetically. Do not list LoRAs, VAEs, embeddings, or other model
> types. Do not generate an image.

SD 1.x candidates:

> List at most 10 installed ComfyUI checkpoints that appear to use the SD 1.x
> architecture. Return exact checkpoint filenames only. Do not generate
> anything.

Grouped candidates:

> Inspect my installed ComfyUI checkpoints and group likely models into SD 1.x,
> SD 2.x, SDXL, Pony/Illustrious, Flux, and Unknown. Return at most 5 exact
> filenames per group. Do not include LoRAs or other model types and do not
> generate anything.

`list_local_models` primarily returns filenames and model categories. An
architecture inferred from a filename is only a likely classification. For a
small candidate set, temporarily enable `model_metadata` and ask the assistant
to verify no more than five exact filenames.

## Defaults and reusable workflows

Temporarily enable `get_defaults` to save a frequently used checkpoint:

> Set the persistent ComfyUI generation defaults to checkpoint
> `BestAll\photoart_V30.safetensors`, width 512, height 512, 15 steps, CFG 6,
> Euler sampler, and normal scheduler. Show the saved values and do not generate
> an image.

Explicit values in a later `generate_image` call override saved defaults.

For a generated API workflow, enable `create_workflow` and `enqueue_workflow`:

> Create a `txt2img` API workflow using checkpoint
> `BestAll\photoart_V30.safetensors`, 512×512, 15 steps, CFG 6, Euler sampler,
> normal scheduler, seed 12345, and prompt “a small stone lighthouse on a
> moonlit coast.” Validate the workflow, enqueue it once, and report its prompt
> ID. Do not submit it more than once.

For a saved workflow, enable `get_workflow` and `enqueue_workflow`:

> Load the saved ComfyUI workflow `[WORKFLOW_FILENAME.json]` in API format,
> summarize its checkpoint and output nodes, then enqueue it once. Do not alter
> the workflow and do not submit it more than once.

Use workflow tools when node-level control is required. For ordinary
text-to-image requests, `generate_image` has a smaller and more reliable call
sequence.

## Result display and local files

After `generate_image` returns its prompt ID, CairnMark handles the remaining
steps without asking the model to poll or guess a filename:

1. wait for the matching `/history/<prompt_id>` record;
2. read the first generated image reference;
3. fetch the original bytes through ComfyUI's `/view` endpoint; and
4. copy those bytes without resizing or re-encoding into CairnMark's
   `instance/preview` directory.

The assistant bubble displays the preview with the existing larger-preview,
reverse-image-search, and download controls. The original ComfyUI output stays
in its own output directory. CairnMark's preview copy is referenced by the chat
so saved and imported conversations can retain their local media association.

## Troubleshooting

- **Service is grey and unavailable:** no start command is saved and the
  configured endpoint is offline. Start ComfyUI manually or save an absolute
  start-command path.
- **Starting ComfyUI... remains visible:** ComfyUI did not expose
  `/system_stats` within the startup window. Check its terminal for startup or
  custom-node errors and verify the endpoint and port.
- **Prompt executed in 0.01 seconds:** inspect history before treating this as
  a failure. With the same fixed seed and workflow, all nodes may be cached and
  the previous output can be returned immediately.
- **The assistant submits the same generation repeatedly:** enable only
  `generate_image` for basic generation and restart CairnMark so the automatic
  history-and-image retrieval logic is active.
- **Checkpoint not found:** copy the exact relative filename reported by
  `list_local_models`, including subfolders and the `.safetensors` extension.
- **No image appears:** confirm that ComfyUI history contains an image output,
  that `/view` can retrieve it, and that the output is PNG, JPEG, WebP, or GIF.
- **Large tool context:** turn off discovery, queue, workflow, model-management,
  and diagnostic tools after use. The quick automatic-scope selection should
  contain only the tools required by the next prompt.
- **Guidance mentions another service:** edit **Tool guidance template** so it
  uses generic wording and retains `{tools}`, for example:

  ```text
  MCP tool access is enabled. Use only the tools listed below:
  {tools}
  ```

For global tool switches, execution limits, and automatic-scope behavior, see
**[MCP tool handling](./mcp-tools.md)**.
