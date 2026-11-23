# Installation, local data, and development

## Requirements

- Python 3.14;
- Git when cloning the repository;
- a running local model server or a hosted-provider API key; and
- FFmpeg on `PATH` for video and audio conversion.

## Windows 11

```powershell
git clone https://github.com/CosmicLaca/CairnMark.git
cd CairnMark
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
.\run.bat
```

## Linux

```bash
git clone https://github.com/CosmicLaca/CairnMark.git
cd CairnMark
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
./run.sh
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the launcher terminal
open and press **Ctrl+C** to stop CairnMark.

To use another port:

```powershell
$env:PORT = "5050"
.\run.bat
```

```bash
PORT=5050 ./run.sh
```

CairnMark intentionally listens only on `127.0.0.1`. It is not a hosted or
multi-user service.

## First session

1. Configure and enable a provider on **Setup models**.
2. Select an enabled model on **Home** and send a test message.
3. Create a small benchmark JSON.
4. Preview it on **Run benchmark**.
5. Run it against an enabled model when the content is correct.

## Local data

| Location | Contents |
| --- | --- |
| `instance/cairnmark.db` | Provider configuration, benchmark metadata, categories, and chat setup |
| `instance/chathistory.db` | Active history, saved chats, and saved system prompts |
| `instance/parameters.db` | Cached local generation parameters |
| `instance/tools.db` | MCP switches, settings, encrypted passwords, and cached definitions |
| `.secret/` | Encryption key for provider and MCP credentials |
| `Benchmark-prompts/` | User benchmark JSON files and optional logs |
| `System-prompts/` | Editable generation, run, evaluation, and compaction prompts |
| `Exported-chat/` | Import-ready conversation exports |
| `services/mcp.json` | Private Custom MCP declarations |

Stop CairnMark before a complete backup. Copy `instance/`, `.secret/`,
`Benchmark-prompts/`, `System-prompts/`, `Exported-chat/`, and
`services/mcp.json` together. Do not publish them; they can contain credentials,
private prompts, attachments, and model responses.

## Troubleshooting

### Port 5000 is busy

Stop the process using it or set another `PORT` before launching.

### A benchmark file is missing

Confirm that it is valid `.json` directly inside `Benchmark-prompts/`.

### More diagnostic logs are needed

Start with `CAIRNMARK_LOG_LEVEL=DEBUG`. Provider keys and request content are
excluded from application logs.

## Development

Show development-only placeholder pages:

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

Automated tests use isolated temporary databases and mocked providers. They do
not require live llama.cpp, vLLM, MCP, or hosted API services.
