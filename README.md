# Cairnmark

> A private, local workspace for chatting with AI models and creating,
> organizing, and running benchmark prompt sets.

**Preview release · single user · localhost only**

Created by Primere Development · [GitHub repository](https://github.com/CosmicLaca/Cairnmark)

---

## What Cairnmark does

Cairnmark brings local and hosted model providers into one browser interface.
You can:

- chat with an enabled model, attach supported files, and save useful chats;
- generate benchmark JSON from topics and custom instructions;
- categorize, filter, inspect, and edit benchmark metadata;
- run benchmark requests sequentially against a selected model; and
- store answers, response times, and optional Markdown logs locally.

Benchmark files stay as readable JSON. Application settings and chat data use
local SQLite databases. Hosted-provider API keys are encrypted at rest.

> **Preview limitation**
>
> Evaluation, result history, and export are under development. Their pages
> appear only in development mode and are not working product features.

## Quick navigation

| I want to… | Go to |
| --- | --- |
| Connect a model | [Set up a provider](#1-set-up-a-provider) |
| Test a model interactively | [Chat on Home](#2-chat-on-home) |
| Generate a benchmark file | [Create a benchmark](#3-create-a-benchmark) |
| Find or edit benchmark metadata | [Browse benchmark files](#4-browse-benchmark-files) |
| Run requests and record answers | [Run a benchmark](#5-run-a-benchmark) |
| Back up or move local data | [Data, privacy, and backups](#data-privacy-and-backups) |
| Fix a common problem | [Troubleshooting](#troubleshooting) |

## Install and start

### Requirements

- Python 3.14;
- Git, if you clone the repository;
- at least one local model server or hosted-provider API key; and
- FFmpeg on `PATH` for video/audio conversion. Cairnmark still starts without
  FFmpeg, but media conversion and audio extraction may be unavailable.

### Windows 11

```powershell
git clone https://github.com/CosmicLaca/Cairnmark.git
cd Cairnmark
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
.\run.bat
```

### Linux

```bash
git clone https://github.com/CosmicLaca/Cairnmark.git
cd Cairnmark
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the launcher terminal
open. Press **Ctrl+C** to stop Cairnmark.

To use another port:

```powershell
$env:PORT = "5050"
.\run.bat
```

```bash
PORT=5050 ./run.sh
```

> Cairnmark intentionally binds only to `127.0.0.1`. It is designed for one
> user on one computer, not as a network or hosted service.

## First session in five steps

1. Open **Setup models** and save a provider connection.
2. Enable the provider and, where shown, enable at least one model.
3. Open **Home** and send a test message.
4. Open **Create benchmark JSON** and generate a small benchmark.
5. Open **Run benchmark**, inspect the file, and run it against an enabled
   model.

## Interface overview

| Page | Purpose |
| --- | --- |
| **Home** | Chat, attachments, saved chats, system prompts, and generation settings |
| **Create benchmark JSON** | Generate benchmark JSON from topics and instructions |
| **Run benchmark** | Filter, inspect, organize, edit, and run benchmark files |
| **Setup models** | Configure providers and choose active models |
| **About** | Read this manual inside Cairnmark |

The sidebar can collapse to an icon rail. In expanded mode, drag its right edge
to resize it. With the resize handle focused, use the arrow keys, or
double-click the handle to restore its default width. The browser remembers the
layout.

---

## 1. Set up a provider

<p align="center"><img src="manual/setup-models.jpg" width="78%" alt="Setup models page"></p>

Cairnmark supports two local providers and ten hosted providers.

| Provider | Connection and model behavior |
| --- | --- |
| **llama.cpp** | Enter a local address and port; discovers and saves multiple models |
| **vLLM** | Enter a local address and port; reads its one loaded model live |
| **OpenRouter, OpenAI, Google Gemini, Anthropic, Mistral** | Enter an API key and fetch the provider catalog |
| **DeepSeek, OpenCode, OpenCode-ZEN, Z.ai, Grok** | Enter an API key and fetch the provider catalog |

### Connect and enable

1. Select a provider card on **Setup models**.
2. Enter the local endpoint or hosted API key.
3. Fetch the catalog and save the configuration.
4. Turn on the provider.
5. For providers with saved catalogs, turn on each model you want to use.

<p align="center"><img src="manual/setup-server.jpg" width="78%" alt="Provider connection dialog"></p>

A model appears on other pages only when its provider and model are enabled.
An unreachable provider cannot remain enabled. vLLM is the exception: Cairnmark
queries its loaded model live, so vLLM has no separate saved model switch.

API keys are never returned to the browser after saving. They are encrypted in
`instance/cairnmark.db` with the key stored under `.secret/`.

---

## 2. Chat on Home

<p align="center"><img src="manual/homepage.jpg" width="78%" alt="Chat home page"></p>

1. Choose an active model in **Chat setup**.
2. Optionally change the system prompt or generation controls.
3. Enter a message and select **Send**.
4. During generation, select **Abort** to request cancellation.

### Standard generation controls

The standard fields are system prompt, temperature, top p, top k, seed, and
recent-message limit. **Save setup** stores only the selected model and these
standard fields as defaults for the next page load. The seed field has a
**Randomize seed** switch; when it is on, each send generates a new seed and
stores the switch state in `instance/cairnmark.db`.

The additional-parameters dialog is session-only:

- **Set** keeps its current inputs for later requests on the same page;
- **Unset** removes those inputs; and
- **Delete from local DB** removes cached defaults for a local model, so the
  next open reads and caches fresh values from the provider.
- **Save settings per model** stores the edited defaults for the selected model
  in `instance/parameters.db`, so they are reused on later opens.

Only allowlisted local sampling fields are forwarded to llama.cpp and vLLM.
Hosted providers ignore these additional local-model values.

### Attach files

The document button is always available. Image, video, and audio buttons appear
when the selected local model reports those capabilities.

| Attachment | Processing |
| --- | --- |
| Image | Images above 1.2 megapixels are resized before sending |
| Video | Re-encoded as MP4, scaled to a 480 px maximum side, reduced to 2 fps, and sent without audio by default |
| Audio | Converted to a 64 kbit/s MP3 when conversion is available |
| Document | Plain-text files are sent directly; supported binary formats are converted to Markdown through a configured MinerU service |

The maximum submitted attachment size is 100 MB, with up to eight attachments
per request.

- **Attach audio** extracts a video's audio and analyzes it in a separate model
  request when necessary.
- **Save the original attachment** saves the processed video/audio under
  `instance/preview/` so a player remains available in chat history.

Both switches remember their last-used values in `instance/cairnmark.db`. Their
values remain selected after removing or sending an attachment and after
restarting Cairnmark.

### Documents and MinerU

The document button is always available. Plain-text files (`.txt`, `.md`,
`.json`, `.csv`, `.tsv`, `.html`, `.xml`, `.rtf`) are sent to the model as
text. Binary formats (PDF, images, Office documents, EPUB, and the other
MinerU-supported types) are converted to Markdown before sending when a MinerU
service is configured.

To use MinerU:

1. Right-click the document button, or click it when no endpoint is saved.
2. Enter the MinerU API endpoint (default `http://127.0.0.1:8100`) and an
   optional API key.
3. Select **Save**. Cairnmark checks the endpoint and stores it only when it
   responds.
4. Attach a supported binary document. Cairnmark shows "Document processing…"
   while MinerU converts it, then "thinking…" while the model replies.

The endpoint and API key are stored in `instance/cairnmark.db` and can be
changed later by right-clicking the document button. Unsupported file types are
rejected before upload.

Small image previews are stored in `instance/preview/`; chat history stores only
their randomized filenames.

### Save chat content

- **Save chat** creates or replaces a named conversation.
- **Saved chats** loads or deletes a stored conversation.
- **Clear chat** clears the current conversation.
- Saved system prompts can be created, loaded, and deleted separately.

---

## 3. Create a benchmark

<p align="center"><img src="manual/create-benchmark.jpg" width="78%" alt="Create benchmark page"></p>

Open **Create benchmark JSON**, then configure:

1. **Category** — choose an existing category or create one.
2. **Difficulty** — choose Easy, Normal, or Hard.
3. **Model** — choose an enabled `provider::model` entry.
4. **Topics** — add topic names and request/response pair counts (1–100 per
   topic).
5. **Prompt customization** — optionally edit the system prompt and generation
   details.

Select **Create benchmark**. Cairnmark reports progress as the model completes
topics and pairs. On success it atomically saves the JSON, records metadata,
and displays the file on **Run benchmark**.

Generated filenames keep the application's historical spelling:

```text
Benchamrk-prompts-YYYYMMDDHHMM-Category-Difficulty.json
```

---

## 4. Browse benchmark files

<p align="center"><img src="manual/view-benchmark.jpg" width="78%" alt="Benchmark browser"></p>

Place imported `.json` files directly in `Benchmark-prompts/`, then reload
**Run benchmark**. Nested directories are not scanned.

Use category tabs and difficulty controls to filter cards. A file without saved
metadata appears under **Uncategorized** with **Normal** difficulty.

- Select the filename area to edit category, difficulty, notes, generation
  prompt, and source-model metadata.
- Select **View benchmark** to open the request/response accordion.
- Edit a reference response in the preview when it needs correction.
- Metadata changes do not move or rewrite the benchmark JSON file.

---

## 5. Run a benchmark

<p align="center"><img src="manual/run-benchmark.jpg" width="78%" alt="Benchmark runner"></p>

Select **Create benchmark** on a benchmark card to open the runner.

1. Choose an enabled model.
2. Review the prompt loaded from `System-prompts/run_benchmark-SYSTEM.md`.
3. Optionally enable **Create log**.
4. Select **Run benchmark** and keep the page open until processing finishes.

Cairnmark runs requests sequentially. It sends only each `request` and the
processed system prompt. It never sends the expected `response` or any other
benchmark key to the model.

Each result is appended to that request's `answers` array:

```json
{
  "model_name": "provider::model",
  "model_answer": "The model output",
  "response_time": 3
}
```

The source JSON is replaced atomically, and keys Cairnmark does not use are
preserved. Optional Markdown logs are written to `Benchmark-prompts/logs/`.

## Benchmark JSON format

The expected document is a top-level array of named topic objects. Each topic
contains a `benchmarks` array:

```json
[
  {
    "Networking": {
      "benchmarks": [
        {
          "request": "Which OSI layer provides end-to-end flow control?",
          "response": "The transport layer (Layer 4).",
          "answer_type": "short_text"
        }
      ]
    }
  }
]
```

Extra keys such as `answer_type` are allowed and remain intact when results are
saved.

---

## Data, privacy, and backups

| Location | Contents |
| --- | --- |
| `Benchmark-prompts/` | Benchmark JSON and appended run answers |
| `Benchmark-prompts/logs/` | Optional run logs |
| `System-prompts/` | Editable default prompt templates |
| `instance/cairnmark.db` | Benchmark metadata, providers, encrypted keys, chat defaults, and attachment preferences |
| `instance/chathistory.db` | Current chat, saved chats, and saved system prompts |
| `instance/parameters.db` | Cached local-model generation defaults |
| `instance/preview/` | Chat image and media previews |
| `.secret/` | Local API-key encryption key |

Content sent to hosted models is subject to that provider's terms and privacy
policy.

### Make a complete backup

1. Stop Cairnmark.
2. Copy `Benchmark-prompts/`, `System-prompts/`, `instance/`, and `.secret/`
   together.
3. Keep `instance/cairnmark.db` and `.secret/` paired; saved API keys cannot be
   decrypted without the matching key.

Do not publish these directories. They may contain prompts, model responses,
provider configuration, and credentials.

## Troubleshooting

### A model does not appear

Confirm that the configuration is saved, the provider is reachable and
enabled, and the model switch is enabled. For vLLM, confirm its server has one
model loaded.

### A benchmark file does not appear

Confirm that it:

- has a `.json` extension;
- is directly inside `Benchmark-prompts/`, not a nested folder; and
- contains valid JSON in the documented structure.

Reload the page after correcting the file.

### Video or audio conversion does not work

Install the FFmpeg executable and confirm `ffmpeg` is available on `PATH` from
the same terminal that starts Cairnmark. The Python package in
`requirements.txt` is a wrapper and does not install the FFmpeg executable.

### Port 5000 is already in use

Stop the earlier process or start Cairnmark with another `PORT`, as shown in
[Install and start](#install-and-start).

### Enable debug logging

```powershell
$env:CAIRNMARK_LOG_LEVEL = "DEBUG"
.\run.bat
```

```bash
CAIRNMARK_LOG_LEVEL=DEBUG ./run.sh
```

Provider keys and request content are not written to application logs.

## Developer reference

Show unfinished pages locally:

```powershell
.\venv\Scripts\python.exe app.py --dev
```

Run the isolated automated suite:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

```bash
venv/bin/python -m pytest -q
```

### Code map

| Area | Responsibility |
| --- | --- |
| `app.py` | Application factory and local launcher |
| `routes.py` | Declarative public URL mapping |
| `controllers/` | HTTP validation, responses, and page context |
| `services/` | Provider protocols and reusable business rules |
| `models/` | SQLite persistence boundary |
| `services/benchmark_documents.py` | Benchmark discovery and atomic file operations |
| `templates/` | Jinja page structure |
| `static/js/` | Browser behavior |
| `static/css/` | Shared shell and route-specific styling |

Tests use temporary databases, benchmark directories, and mocked provider
clients. They must not require live local or hosted model services.

## Roadmap

Planned but not currently available:

- evaluate recorded answers against reference responses;
- browse previous runs and scores; and
- export benchmark results.

Authentication, hosted multi-user deployment, and production service mode are
outside Cairnmark's current local, single-user scope.

---

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

The terms below are authoritative.

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
3. **No modification.** You may not modify, adapt, translate, reverse engineer,
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
