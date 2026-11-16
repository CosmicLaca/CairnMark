# CairnMark
## The personal local AI benchmark system

---

**Creator: Primere Development**

**GIT:** `https://github.com/CosmicLaca/Cairnmark`

---

## Preview version, under development

A local workbench for building, organizing and running LLM benchmark sets.

Cairnmark is a Flask application that lets you chat with a model, have a model
generate benchmark JSON, organize those files, and run them against any
configured model, local or hosted. Everything stays on your machine: provider
settings, benchmark metadata and chat history live in local SQLite files, and
benchmarks are plain JSON.

## Contents

- [At a glance](#at-a-glance)
- [Project status](#project-status)
- [Quick start](#quick-start)
- [Installation](#installation)
- [Running Cairnmark](#running-cairnmark)
- [Typical workflow](#typical-workflow)
- [Interface](#interface)
- [Model providers](#model-providers)
- [Chat](#chat)
- [Creating benchmarks](#creating-benchmarks)
- [Benchmark files](#benchmark-files)
- [Running a benchmark](#running-a-benchmark)
- [Data and storage](#data-and-storage)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

## At a glance

- **Twelve providers:** llama.cpp and vLLM locally, plus ten online providers,
  all configured on one page.
- **SDK-backed access:** discovery, reachability checks, chat, benchmark
  generation and benchmark runs all go through the providers' Python SDKs.
  Cairnmark does not issue raw outbound HTTP requests to model providers.
- **Plain-JSON benchmarks:** a benchmark is a JSON file in `Benchmark-prompts/`.
  Category, difficulty and notes are metadata kept in SQLite, so organizing a
  file never rewrites it.
- **Blind runs:** a run sends the model only the request text and the system
  prompt. The expected response is never sent.
- **Local-first storage:** API keys are encrypted at rest, and logs never
  contain keys or request contents.
- **File attachments in chat:** attach images, documents, video and audio
  files to a request; image previews are stored separately and only their
  filenames are kept in the chat database.

## Project status

| Feature | Status |
| --- | --- |
| Chat with an active model | Available |
| Provider setup (12 providers) | Available |
| Create benchmark JSON | Available |
| Organize, inspect and run benchmarks | Available |
| Evaluate benchmark | Placeholder |
| Previous benchmarks | Placeholder |
| Export benchmark results | Placeholder |

The Evaluate, Previous benchmarks and Export benchmark results pages are
informational placeholders. Do not treat them as working features.

## Quick start

```bash
git clone https://github.com/CosmicLaca/Cairnmark.git
cd Cairnmark
python3 -m venv venv && source venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

Then open <http://127.0.0.1:5000>. Windows commands and details are in
[Installation](#installation).

## Installation

Cairnmark runs on Python and the packages in `requirements.txt`. The included
virtual environment uses Python 3.14.

### Clone the repository

```bash
git clone https://github.com/CosmicLaca/Cairnmark.git
cd Cairnmark
```

To update an existing copy later:

```bash
git pull
```

### Create the virtual environment

This is a one-time step. Run it in PowerShell (Windows) or a shell (Linux).

**Windows 11:**

```powershell
python -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip
```

**Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
```

### Install dependencies

With the virtual environment active (Windows and Linux):

```powershell
python -m pip install -r requirements.txt
```

## Running Cairnmark

**Windows:**

```powershell
.\run.bat
```

**Linux:**

```bash
./run.sh
```

Open <http://127.0.0.1:5000>. Keep the launcher terminal open while you work.
Press **Ctrl+C**, or close the terminal, to stop the server and release the
port.

### Using a different port

The default port is `5000`. Set `PORT` for the current launch:

**Windows:**

```powershell
$env:PORT = "5050"
.\run.bat
```

**Linux:**

```bash
PORT=5050 ./run.sh
```

Then open the matching address, for example <http://127.0.0.1:5050>.

## Typical workflow

1. **Set up providers.** Add the local servers or API keys you need on
   **Setup models**, then switch on the models you want to use.
2. **Create a benchmark.** Pick a category, difficulty, model and topics on
   **Create benchmark JSON**. The model generates the request-response pairs.
3. **Organize.** Review the new file on **Run benchmark**, and set its
   category, difficulty and notes.
4. **Run.** Choose a model and system prompt. Each answer is appended to the
   same JSON file together with the model name and response time.
5. **Evaluate.** Planned; see the [Roadmap](#roadmap).

## Interface

The side menu has an icon-only mode and an expanded icon-and-text mode.

- Select the circular menu control to switch modes.
- In expanded mode, drag the menu's right edge to change its width.
- With the resize grip focused, use the arrow keys for precise adjustment.
- Double-click the grip to restore the default width.

The browser remembers the menu mode and width on the current device.

| Page | Purpose |
| --- | --- |
| Home | Chat with an active model |
| Create benchmark JSON | Choose a category, difficulty and model, then generate a benchmark JSON |
| Run benchmark | Organize, filter, inspect and run benchmark JSON files |
| Evaluate benchmark | Placeholder |
| Previous benchmarks | Placeholder |
| Export benchmark results | Placeholder |
| Setup models | Configure llama.cpp, vLLM and online provider model catalogs |
| About | Displays this user manual |

## Model providers

The **Setup models** page supports twelve providers.

| Provider | Connection | Saved model behavior |
| --- | --- | --- |
| llama.cpp | Local OpenAI-compatible `/v1/models`, port `8080` by default | Saves multiple model names and their individual on/off states |
| vLLM | Local OpenAI-compatible `/v1/models`, port `8001` by default | Reads the single currently loaded model live; no model switch is shown |
| OpenRouter | Online catalog, API key | Saves selected model names and their individual on/off states |
| OpenAI | Online catalog, API key | Saves selected model names and their individual on/off states |
| Google Gemini | Gemini API catalog, Google AI Studio API key | Saves text-generation model names and their individual on/off states |
| Anthropic | Online catalog, API key | Saves selected model names and their individual on/off states |
| Mistral | Online catalog, API key | Saves selected model names and their individual on/off states |
| DeepSeek | Online catalog, API key | Saves selected model names and their individual on/off states |
| OpenCode | OpenCode Console catalog, Console API key | Saves selected model names and their individual on/off states |
| OpenCode-ZEN | Zen gateway catalog, Zen API key | Saves selected model names and their individual on/off states |
| Z.ai | Online catalog, API key | Saves selected model names and their individual on/off states |
| Grok | Online catalog, API key | Saves selected model names and their individual on/off states |

### SDK usage

- Native Python SDKs: OpenRouter, OpenAI, Google Gemini, Anthropic, Mistral
  and Grok.
- OpenAI Python SDK against the documented OpenAI-compatible service URLs:
  llama.cpp, vLLM, DeepSeek, OpenCode, OpenCode-ZEN and Z.ai.

### Configure a provider

1. Open **Setup models** and select the provider's **Configure provider**
   button.
2. For llama.cpp or vLLM, enter the server address and port. For an online
   provider, enter the API key issued by that provider.
3. Select **Read Models**. This reads the live provider catalog; it does not
   reload the saved SQLite list.
4. Search the catalog by model name, then enable individual models or use
   **Select All**. vLLM always uses its one loaded model.
5. Select **Save Configuration**. The modal closes and the provider card shows
   the saved total and active model counts. vLLM shows its live model name.
6. Use the provider-level switch to turn the whole provider on or off.

Opening a saved configuration restores its model list and switches. Online
providers never display the saved API key. Leave the field blank to reuse it,
or enter a new key to replace it.

### Provider states

The provider tabs summarize live state:

- `online::on`: the endpoint is reachable and the provider is enabled.
- `online::off`: the endpoint is reachable but the provider is disabled.
- `offline`: setup is incomplete or the endpoint cannot be reached.

The provider-level switch becomes available only after a valid configuration
is saved and its endpoint is reachable. An unavailable provider is forced off
and its switch is disabled until it is reachable again. Reading models does not
run them or send benchmark prompts.

### Provider-specific notes

**Grok** uses xAI (`api.x.ai`), not Groq (`api.groq.com`). Create its key in
the xAI Console. Cairnmark rejects `gsk_` Groq keys before sending a request.

**OpenCode and OpenCode-ZEN** use different service routes and may use
different key types. Use a current OpenCode Console personal or service-account
key for **OpenCode**, and a Zen key for **OpenCode-ZEN**. Do not assume the
keys are interchangeable. Their catalogs are read from
`https://opencode.ai/inference/v1/models` and
`https://opencode.ai/zen/v1/models`, respectively.

- HTTP 401: the key was rejected.
- HTTP 403: the request is authenticated, but the key usually lacks
  permission, billing or model access.

## Chat

Open **Home** to chat with an active model. The history is in the middle of the
page; the model selector, system prompt and parameters are on the right.

### Model and system prompt

The **Model** dropdown is filled from saved provider settings, with the same
rules as **Create benchmark JSON**, including the live vLLM model. The
provider and the model must both be switched on.

The **System prompt** textarea holds the instructions sent with every request.
**Save setup** persists the selected model, system prompt and generation
parameters to `instance/cairnmark.db`, and restores them as the page defaults
on the next visit. Additional parameters set through **Set more parameters** are
session-only and are never saved by **Save setup**.

System prompts can be stored under a name with **Save system prompt** and
reused from the **Saved system prompts** dropdown. **Delete** removes one.
Selecting a saved prompt fills the textarea, and editing the textarea clears
the selection. The prompt's name is shown on an assistant reply when the text
still matches.

### Parameters

Numeric inputs control the request: **Temperature**, **Top P**, **Top K**,
**Seed** and **Recent messages kept**. Fields with a value are sent with every
message. An empty field omits that parameter from the request, and the saved
setup keeps it empty until you enter a value again.

**Recent messages kept** limits how many previous messages are included with a
new request (default 4). Leave it empty to send the full history.

**Set more parameters** opens the additional generation settings reported by a
local llama.cpp or vLLM model:

- The first successful read is cached in `instance/parameters.db` under the
  selected `provider::model` key. Later opens use the cached defaults without
  contacting the provider.
- When values come from that cache, **Delete from local DB** removes the saved
  entry and re-reads the parameters from the model server.
- **Save** hides the dialog and keeps the edited values for the following chat
  requests. **Cancel** discards them. These overrides are session-only.
- Only the values currently present in the dialog are applied. Supported
  sampling overrides are forwarded to llama.cpp and vLLM; other providers
  ignore them.

The **Model** label can also show the model's context size as `Model | N ctx: 8192`
when it is available from the saved parameter data. If the llama.cpp server was
started with a different configuration, this value can be stale. Use **Set more
parameters**, then **Delete from local DB**, to re-read all parameters, including
`n_ctx`, from the server.

The button shows a status sign:

| Sign | Meaning |
| --- | --- |
| Disabled | The parameter list cannot be read from the local server |
| SET | Parameter inputs are active and will be sent with the next request |
| UNSET | No inputs are active; the request omits them |

### Sending messages

Type a message and select **Send** (or press Enter). The reply is appended to
the history and rendered as Markdown by default. Use **Raw** to see the source.

Each reply shows the model name, response time, and input and output token
counts, plus:

- a **Copy** button,
- an icon that opens the system prompt actually used, rendered as Markdown,
- an icon that opens the **API Body request** modal with the full JSON request
  body sent for that turn.

While the model works, the spinner shows the number of output tokens generated
so far, and **Abort** cancels the request.

### File attachments

The media icons below the message input let you attach files to a request:

- **Document** is always available and opens a file dialog filtered to
  `.txt`, `.md`, `.doc`, `.rtf` and `.docx`.
- **Image**, **video** and **audio** icons appear only when the selected
  local model reports that capability. Image opens image files, video opens
  `.mp4` files, and audio opens `.mp3` and `.wav` files.

Selecting a file adds it to the request. Images are resized automatically
when they are larger than 1.2 megapixels. The attached file is shown as a
small preview or filename chip next to the message input and is included with
the request.

In the conversation, an attached image is shown as a small preview on the left
side of the user message. That preview is saved to `instance/preview/` and
only its filename is stored in the chat database, so chat history stays
small. If a preview file is later missing, a broken-link icon is shown
instead of the image.

### Saved chats

- **Save chat** stores the conversation under a name, overwriting an existing
  name.
- **Saved chats** lists stored conversations; selecting one loads its history.
- **Delete chat** removes the selected saved chat.
- **Clear chat** empties the current conversation.

## Creating benchmarks

Open **Create benchmark JSON** to generate a benchmark with a model.

### Category

The **Category** dropdown lists the collections already used by saved
benchmarks. To create one before any benchmark file exists, choose
**＋ Add new category**, enter a name and select **Create category**. New
categories are stored in `instance/cairnmark.db` and also appear in the
category selector when you organize an existing benchmark.

### Model

The **Model** dropdown is filled from saved provider settings:

- The provider must be switched on in **Setup models**.
- The individual model switch must also be on.
- Each entry is shown as `provider::model`, for example
  `llama.cpp::Gemma-4-31B-Fable-Coder.Q5_K_M` or
  `OpenRouter::Baidu: ERNIE-5.5-Flash-Preview (free)`.

Enabled saved models from llama.cpp, OpenRouter, OpenAI, Google Gemini,
Anthropic, Mistral, DeepSeek, OpenCode, OpenCode-ZEN, Z.ai and Grok appear in
the list. When vLLM is switched on and its server is reachable, its one loaded
model is read live and appears as `vLLM::<model name>`. It is not stored as a
saved model switch. If no provider or model is active, the page shows an empty
state with a link to **Setup models**.

### Difficulty

Choose **Easy**, **Normal** or **Hard**. The selection is saved with the
generated benchmark and used consistently across benchmarks.

### Topics

Each main topic becomes a first-level section in the generated JSON. For each
topic, enter a name and the number of request-response pairs to create
(1 to 100). Use **Add topic** for more rows and the trash icon to remove rows.
At least one filled topic is required; empty rows are ignored.

### Prompt customization (optional)

Two multiline inputs override the built-in prompts:

- **System prompt**: instructions that shape the generated benchmark JSON.
- **Request-response creation details**: guidance for how each topic's
  request-response pairs are authored.

Leave both empty to use the defaults. When you select **Create benchmark**, the
fields are filled from the default templates, with the chosen category,
difficulty and topics substituted in. You can review them before generation;
they become read-only while the model runs.

### Generate

Select **Create benchmark** to validate the configuration and send the system
and user prompts to the selected model. The button is disabled while the model
runs. Cairnmark first checks that the provider server is online and shows an
alert if it is not. While running, the page shows a progress message with the
topic currently being generated and its completed request-response pairs out of
the total (for example, `Physics 1 / 3`).

When generation finishes, Cairnmark:

1. saves the returned JSON to `Benchmark-prompts/` as
   `Benchamrk-prompts-{{datetime}}-{{category}}-{{difficulty}}.json` (the
   spelling is the one the application emits),
2. records its metadata (category, difficulty, generation prompt, model name)
   in `instance/cairnmark.db`,
3. shows a success message with the filename and resets the topic and prompt
   inputs to their defaults.

The new file then appears on **Run benchmark**.

## Benchmark files

### Adding files

Place `.json` files directly in `Benchmark-prompts/` and reload **Run
benchmark**. Files in subdirectories are not listed.

### File format

For the built-in viewer, a benchmark has named top-level sections. Each section
holds numbered entries with `request` and `response` values:

```json
[
  {
    "Telecommunication": {
      "benchmarks": [
        {
          "request": "Explain the fundamental difference between Multiplexing and Modulation in signal transmission.",
          "response": "Multiplexing is the process of combining multiple signals into a single signal over a shared medium to increase capacity, whereas Modulation is the process of varying a carrier signal's properties (such as amplitude, frequency, or phase) to encode information for transmission."
        },
        {
          "request": "In the OSI model, which layer is responsible for end-to-end error recovery and flow control?",
          "response": "The Transport Layer (Layer 4)."
        }
      ]
    }
  }
]
```

### Organizing files

Open **Run benchmark** from the side menu.

1. Choose a collection category at the top of Benchmark Selection. Only
   categories that contain files are shown, and the first populated category is
   selected initially.
2. Optionally choose **All**, **Easy**, **Normal** or **Hard** below the
   collection heading. Only difficulty values present in the selected
   collection are offered. **All** disables difficulty filtering.
3. Select a file's filename area to open its details page.
4. Choose an existing category, or use **Add new category** and enter a name.
5. Set the difficulty. New files use **Normal** until saved.
6. Optionally record the generation prompt that produced the JSON and the model
   that generated it.
7. Add optional notes and save.

Files without saved metadata appear in **Uncategorized**. Moving a file to a
category changes only Cairnmark's local metadata; it does not move or rewrite
the JSON file.

Hover over or focus a file's filename area to see its category, difficulty and
notes (when it has saved metadata). The **View benchmark** control does not
show the notes tooltip.

### Viewing contents

Select **View benchmark** inside a file card to display its formatted content
below Benchmark Selection. Each top-level JSON key becomes an accordion; open
it to inspect its request and response pairs. Only one file is displayed at a
time: selecting **View benchmark** on another card replaces the current
viewer, and the close control hides it.

## Running a benchmark

Select **Create benchmark** on a file card to open the **Create benchmark
setup** panel. There you choose an active model, optionally adjust the system
prompt, and run the file.

1. **Choose a model.** The dropdown is filled from saved provider settings.
   vLLM contributes its one live model while its server is reachable. The
   provider and the model must both be switched on.
2. **Review the system prompt.** It is pre-filled from
   `System-prompts/run_benchmark-SYSTEM.md`, with the file's category and
   difficulty substituted in. The `{{subcategory}}` placeholder is replaced per
   topic while the benchmark runs.
3. **Optionally enable Create log** to write a readable Markdown log.
4. **Select Run benchmark.** Cairnmark processes every request in every topic
   one by one and sends the model only the request text and the system prompt.
   The expected response is never sent. The panel shows progress as
   `topic: processed/total`.

For each request, Cairnmark appends an entry to that request's `answers` array:

| Key | Content |
| --- | --- |
| `model_name` | The model that answered |
| `model_answer` | The model's response |
| `response_time` | Response time in seconds |

When all requests are processed, the JSON file is overwritten in place and its
metadata (category, difficulty, generation prompt, model name) is saved to
`instance/cairnmark.db`.

If **Create log** is enabled, a Markdown log is written to
`Benchmark-prompts/logs/` with the same base filename and a `.md` extension. It
records each request, the system prompt used, the model, its response and the
response time.

## Data and storage

| Location | Content |
| --- | --- |
| `Benchmark-prompts/` | Benchmark JSON files, including recorded answers |
| `Benchmark-prompts/logs/` | Optional Markdown run logs |
| `System-prompts/` | Default prompt templates |
| `instance/cairnmark.db` | Category, difficulty, notes, generation prompt, model name, provider settings, model switch states, encrypted API keys, chat page defaults |
| `instance/chathistory.db` | Chat history and saved chats; each assistant message also records the request body used for its reply |
| `instance/parameters.db` | Cached default generation parameters for local provider models |
| `instance/preview/` | Small JPEG previews for images attached in chat |
| `.secret/` | Encryption key for API keys; created on first use and excluded from Git |

Online-provider API keys are encrypted at rest with the key in `.secret/`.
Protect both the database and the `.secret/` directory as you would protect the
keys themselves. The databases are created automatically.

**Backup.** To preserve metadata, provider settings and chat setup defaults when
copying Cairnmark, include `instance/cairnmark.db`. Stop the server before
copying it.

**Reset.** To clear all saved metadata and provider configurations, stop
Cairnmark, delete `instance/cairnmark.db` and start Cairnmark again. Startup
creates a new empty database.

## Troubleshooting

### Enable more application logging

The default log level is `INFO`. Set `CAIRNMARK_LOG_LEVEL=DEBUG` before
starting the server to diagnose provider requests or benchmark failures.
Provider API keys and request contents are never included in these logs.

### Run the test suite

Use the project virtual environment:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

```bash
venv/bin/python -m pytest -q
```

The tests use isolated SQLite files and mock provider catalogs. They do not
contact local model servers or online APIs.

### The port is already in use

Stop the earlier Cairnmark terminal with Ctrl+C. If another application needs
port 5000, launch Cairnmark with a different `PORT` value as shown above.

### A new JSON file is not listed

Confirm that the filename ends in `.json` and that the file is directly inside
`Benchmark-prompts/`, then reload the Run benchmark page.

### A benchmark cannot be displayed

Check that the file contains valid JSON. The accordion viewer works best with
named top-level sections and entries containing `request` and `response`
values.

### A recent file or interface change is not visible

Refresh the browser. If the application files themselves changed, stop the
server and launch it again.

## Roadmap

These items are design intent, not implemented features.

- **Evaluate benchmark:** score each recorded answer against its reference
  `response`, using deterministic checks for exact values and embedding-based
  similarity for open-ended answers, with per-answer scores and the method used
  stored alongside the results.
- **Previous benchmarks:** browse earlier runs and their results.
- **Export benchmark results:** export scores and run data.

## License

Copyright (c) 2026 Primere development. All rights reserved.

Cairnmark is proprietary software developed by **Primere development** (the
"Developer"). The source is visible for inspection, but Cairnmark is not
open-source software. By installing or running it, you accept the terms below.

### Summary

| You may | You may not |
| --- | --- |
| Install and run Cairnmark on one machine, locally, at no cost and without time or usage limits | Run it on more than one machine under one grant, or give anyone else access to it |
| Use it yourself, including for your own professional work | Share an instance between users, including through a cloud, hosted or shared-service setup, or over an internal network |
| Use the application's own settings and edit your benchmark files, prompts and results | Modify, adapt or create derivative works of the software |
| Keep a private backup copy | Redistribute, sell, lease or sublicense it, or offer it as a paid service |

This summary is for convenience. The terms below are authoritative.

### Terms

1. **Grant.** The Developer grants you a non-exclusive, non-transferable,
   revocable license to install and run one copy of Cairnmark on one machine,
   locally, for one user. The license is free of charge and has no time or
   usage limit.
2. **Single machine, single user.** Only the person who runs Cairnmark may use
   it, and only on the machine where it is installed. You may not make an
   instance available to other people in any form: not over the internet, not
   over a local or internal network, not as a hosted, cloud or shared service,
   and not through remote-access, tunneling or proxy setups that give others
   access to it.
3. **No modification.** You may not modify, adapt, translate, reverse engineer
   or create derivative works of Cairnmark, in whole or in part, and you may not
   remove or alter copyright notices. Only the Developer may modify and release
   Cairnmark. The following is not modification: configuring Cairnmark through
   its own interface, editing the prompt template files in `System-prompts/`,
   and creating or editing your own data (benchmark files, logs and the local
   databases it manages).
4. **No redistribution.** You may not copy, publish, sublicense, sell, lease,
   lend or otherwise distribute Cairnmark or any part of it, except for the
   installed copy and a private backup copy for your own use.
5. **No paid service.** You may not offer Cairnmark, or access to it, as a paid
   or otherwise commercial service. This includes selling, renting or charging
   for access, bundling it into a paid product, and operating it as a hosted or
   managed service.
6. **Your data.** The benchmark files, prompts, answers, logs and results you
   create belong to you. This license covers the software only. Content you
   send to or receive from model providers is subject to those providers'
   terms.
7. **Third-party components.** The packages listed in `requirements.txt` are
   licensed by their respective authors under their own terms. This license does
   not change those terms.
8. **Termination.** The license ends automatically if you breach these terms.
   You must then stop using Cairnmark and delete all copies.
9. **No warranty.** Cairnmark is provided "as is", without warranty of any
   kind, express or implied, including merchantability, fitness for a
   particular purpose and non-infringement.
10. **Limitation of liability.** To the extent permitted by law, the Developer
    is not liable for any damages, including data loss or incorrect benchmark
    results, arising from the use of or inability to use Cairnmark.
11. **Reservation of rights.** All rights not expressly granted are reserved by
    the Developer. For other licensing, such as multi-user, team or commercial
    use, contact Primere development at `[contact e-mail or URL]`.
