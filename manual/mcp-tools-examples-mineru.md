# MinerU MCP installation and test examples

This guide prepares four MinerU MCP choices for CairnMark:

1. `mineru-selfhosted-mcp`, a bridge to a MinerU API that you control;
2. `mineru-mcp`, the older community package with local and cloud modes;
3. `mineru-open-mcp`, MinerU's official cloud MCP service; and
4. `mineru-fastmcp-wrapper`, a small local wrapper for a compatible synchronous
   MinerU endpoint.

The commands below are instructions only. CairnMark does not install these
packages automatically, and the repository does not contain downloaded MCP
packages, private service declarations, tokens, or generated documents.

The current package descriptions are available on PyPI for
[`mineru-selfhosted-mcp`](https://pypi.org/project/mineru-selfhosted-mcp/),
[`mineru-mcp`](https://pypi.org/project/mineru-mcp/), and
[`mineru-open-mcp`](https://pypi.org/project/mineru-open-mcp/). MinerU's current
self-hosted API is documented in the
[official MinerU repository](https://github.com/opendatalab/MinerU).

> **Document privacy:** `mineru-open-mcp` sends documents to MinerU's cloud.
> `mineru-selfhosted-mcp`, `mineru-mcp` in local mode, and the wrapper send
> documents to the exact API address saved in their CairnMark setup fields.
> Verify that address before enabling a service.

## Benefits and quick comparison

The four MCP options make MinerU callable by the chat assistant instead of
requiring a separate manual upload-and-copy workflow:

- `mineru-selfhosted-mcp` provides the broadest automation for a current
  self-hosted MinerU API, including health, parsing, staged uploads, libraries,
  and maintenance tools.
- `mineru-mcp` provides a small two-tool interface for older compatible MinerU
  APIs and includes OCR-language discovery.
- `mineru-open-mcp` provides official cloud parsing without operating a local
  MinerU server and is convenient for non-confidential test documents.
- `mineru-fastmcp-wrapper` is minimal and easy to audit or customize when the
  local API has a simple synchronous parse route.

| Option | Processing location | Main benefit | Compatible API | Best use | Main limitation |
| --- | --- | --- | --- | --- | --- |
| `mineru-selfhosted-mcp` | Your local or remote self-hosted server | Most complete tool set and best automation | Current task-based MinerU APIs such as `/v1/tasks` | Repeated private-document workflows controlled from chat | More tools and configuration than a simple upload requires |
| `mineru-mcp` | Local API in local mode; cloud in remote mode | Simple parsing plus OCR-language discovery | Legacy local APIs exposing `/file_parse` | Testing an older compatible MinerU deployment | Version 1.0.0 needs dependency and stdio workarounds and does not parse through MinerU 4.1.7 |
| `mineru-open-mcp` | MinerU cloud | Official service with no local MinerU server to maintain | MinerU cloud API | Quick tests with public or non-confidential files | Documents leave the machine; Flash mode has file and output limits |
| `mineru-fastmcp-wrapper` | Your configured MinerU server | Small, auditable code with one focused tool | Synchronous `/file_parse` or `/v1/file_parse` | A custom or legacy API with a known response format | Must be adapted for task-based APIs and different response formats |
| Local MinerU without MCP | Your local MinerU server | Fewest components, dependencies, and protocol layers | Whatever the local upload client directly supports | One-off uploads when you only need the converted document | The assistant cannot initiate parsing, select tools, check status, or automate follow-up steps |

For a single uploaded document, direct local MinerU without MCP is usually the
better choice: it starts faster, has fewer failure points, avoids MCP tool
selection and context overhead, and exposes API errors more directly. Use MCP
when the assistant should repeatedly choose documents, launch parsing, inspect
health, process several files, or continue automatically with the returned
Markdown. For MinerU 4.1.7, prefer `mineru-selfhosted-mcp` when those automated
capabilities are needed.

---

## 1. Prepare PowerShell and uv

Open PowerShell in the CairnMark repository root:

```powershell
Set-Location "C:\path\to\CairnMark"
$ProjectRoot = (Get-Location).Path
```

Check Python and uv:

```powershell
py --version
uv --version
uvx --version
```

If uv is missing, install it, reopen PowerShell, and recreate `$ProjectRoot`:

```powershell
winget install --id=astral-sh.uv -e
```

Record absolute executable paths. CairnMark's **Command** field should always
use an absolute path:

```powershell
$Uvx = (Get-Command uvx).Source
$Python = (Get-Command py).Source
$Uvx
$Python
```

In CairnMark, open **Home → MCP settings → Add new custom MCP service**. Enter
the service name exactly as shown in this guide. The exact name selects its
committed `static/tool-setup-*.json` setup panel. After saving a new service,
refresh its tools, enable the required subtools, and save MCP settings.

---

## 2. Self-hosted bridge: `mineru-selfhosted-mcp`

This is the recommended option when the MinerU API runs on your machine or on
a server that you control. The current package exposes health, document,
directory, staged-upload, OCR-language, and cleanup tools.

### Prepare the uv cache

```powershell
$SelfHostedCache = Join-Path $ProjectRoot "mcp_tools\mineru-selfhosted-mcp\cache"
New-Item -ItemType Directory -Path $SelfHostedCache -Force | Out-Null

& $Uvx --isolated --cache-dir $SelfHostedCache "mineru-selfhosted-mcp"
```

After the package downloads and the stdio server starts, press `Ctrl+C`. Print
the offline Args value:

```powershell
ConvertTo-Json -InputObject @(
    "--offline",
    "--isolated",
    "--cache-dir",
    $SelfHostedCache,
    "mineru-selfhosted-mcp"
) -Compress
```

### CairnMark service values

| Field | Value |
| --- | --- |
| Name | `mineru-selfhosted-mcp` |
| Timeout (ms) | `1800000` |
| Command | Absolute path printed as `$Uvx` |
| Args | Complete one-line JSON printed above |

The setup panel supplies these process environment values:

| Setup field | Local test value | Remote self-hosted test value |
| --- | --- | --- |
| MinerU API base URL | `http://127.0.0.1:8000` | `http://YOUR-SERVER:8000` |
| MinerU API key (current releases) | Empty unless required | Server token if required |
| MinerU API token (legacy releases) | Empty | Only for a release that documents `MINERU_API_TOKEN` |
| API timeout (seconds) | `1800` | `1800` |
| Inherit proxy environment | Off | Off unless the bridge must use a configured proxy |
| Log directory | Optional local absolute path | Optional local absolute path |
| Published download directory | Empty for local stdio | Set only for hosted HTTP mode |
| Published download base URL | Empty for local stdio | Public download URL for hosted HTTP mode |
| Temporary ZIP lifetime | `10800` | `10800` |
| MCP transport | `stdio` | `stdio` when CairnMark launches the bridge |
| HTTP bind host / port | Leave defaults | Used only when separately hosting the MCP server |
| Staged upload directory | Optional | Server-side directory in hosted HTTP mode |

**Always set MinerU API base URL explicitly.** Some published releases default
to an external IP address. Never rely on that default: an omitted address can
send documents to a server you do not control. Current releases document
`MINERU_API_KEY`; older releases used `MINERU_API_TOKEN`. Set only the field
supported by the installed release.

For remote testing, first verify the remote API yourself without uploading a
document:

```powershell
Invoke-RestMethod "http://YOUR-SERVER:8000/v1/health"
```

Prefer a VPN, SSH tunnel, or HTTPS reverse proxy. Do not expose an unauthenticated
MinerU API directly to the public internet.

### Test prompts

Health-only test:

> Call `mineru_health`. Report the configured API address, response status, and
> service version or capabilities. Do not upload or parse a document.

Local parsing test:

> Parse the local document at `C:/absolute/path/test.pdf`. Return Markdown,
> preserve headings and tables, and report the exact MinerU tool called,
> elapsed time, completed file count, and failed file count.

Remote bridge test:

> Use the configured self-hosted MinerU service to parse
> `C:/absolute/path/test.pdf`. Return only the first two headings and the first
> paragraph, then report whether a ZIP or download URL was created.

Cleanup test:

> List what the MinerU log cleanup tool would remove when keeping the last
> seven days. Do not delete anything unless the tool supports a dry run; if it
> does not, explain that and stop.

---

## 3. Community package: `mineru-mcp`

This package provides `parse_documents` and `get_ocr_languages`. Its local
mode is controlled by `USE_LOCAL_API=true`. PyPI contains similarly named
packages and forks, so confirm that the installed package is exactly
[`mineru-mcp`](https://pypi.org/project/mineru-mcp/) and review its maintainer
and routes before processing private files.

### Install into an isolated application-local environment

```powershell
$CommunityRoot = Join-Path $ProjectRoot "mcp_tools\mineru-mcp"
$CommunityVenv = Join-Path $CommunityRoot ".venv"
New-Item -ItemType Directory -Path $CommunityRoot -Force | Out-Null

py -m venv $CommunityVenv
$CommunityPython = Join-Path $CommunityVenv "Scripts\python.exe"
& $CommunityPython -m pip install --upgrade pip
& $CommunityPython -m pip install "mineru-mcp==1.0.0" "pydantic==2.13.5"
& $CommunityPython -m mineru.cli --help
```

The help output confirms that the package imports successfully without starting
the server.

### CairnMark service values

| Field | Value |
| --- | --- |
| Name | `mineru-mcp` |
| Timeout (ms) | `1800000` |
| Command | Absolute path stored in `$CommunityPython` |
| Args | `["-c","from mineru.server import run_server; run_server('stdio')"]` |

Use these setup values for your local service:

| Setup field | Value |
| --- | --- |
| Use local MinerU API | On |
| Local MinerU API base URL | `http://127.0.0.1:8100` for the local MinerU 4.1.7 example |
| Remote MinerU API base URL | Leave at the default; ignored in local mode |
| MinerU API key or local placeholder | `local` |
| Output directory | `mcp_tools/mineru-mcp/output` |

The package CLI writes startup banners to standard output, which corrupts the
stdio MCP protocol. The alternative Args value above starts its server directly
and keeps standard output reserved for MCP messages. Version 1.0.0 also refuses
to start without `MINERU_API_KEY`, including in local mode; the non-empty
`local` placeholder satisfies that startup check and is not sent to the local
`/file_parse` route.

`mineru-mcp==1.0.0` currently installs an older MCP SDK that is incompatible
with Pydantic 2.14. Pinning Pydantic to 2.13.5 prevents the MCP process from
failing during import. To repair an existing application-local environment,
run:

```powershell
& $CommunityPython -m pip install --upgrade "pydantic==2.13.5"
```

This dependency pin fixes process startup only. The community package posts
documents to `/file_parse`, while MinerU 4.1.7 exposes its processing workflow
through `/v1/tasks`. Therefore, the community package cannot parse documents
with the `http://127.0.0.1:8100` MinerU 4.1.7 API even though
`/v1/health` reports healthy. Use `mineru-selfhosted-mcp` for this API, or run a
legacy MinerU API that implements `/file_parse` when testing the community
package.

Test prompts:

> Call `get_ocr_languages` and show five language codes, including English if
> available. Do not parse a document.

> Using local API mode, parse `C:/absolute/path/test.pdf` with OCR disabled and
> language `en`. Return the Markdown title and first paragraph, and state the
> output directory.

---

## 4. Official cloud service: `mineru-open-mcp`

This is MinerU's official MCP package, but it is not self-hosted. It sends the
selected document to MinerU's cloud service. Without a token it uses Flash
mode: Markdown-only output with a maximum of 20 pages and 10 MB. The current
[MinerU API documentation](https://mineru.net/apiManage/docs) describes those
Flash limits. Do not use this mode for confidential documents.

### Prepare the uv cache

```powershell
$OpenCache = Join-Path $ProjectRoot "mcp_tools\mineru-open-mcp\cache"
New-Item -ItemType Directory -Path $OpenCache -Force | Out-Null

& $Uvx --isolated --cache-dir $OpenCache "mineru-open-mcp"
```

Press `Ctrl+C`, then print the offline Args value:

```powershell
ConvertTo-Json -InputObject @(
    "--offline",
    "--isolated",
    "--cache-dir",
    $OpenCache,
    "mineru-open-mcp"
) -Compress
```

### CairnMark service values

| Field | Value |
| --- | --- |
| Name | `mineru-open-mcp` |
| Timeout (ms) | `1800000` |
| Command | Absolute path printed as `$Uvx` |
| Args | Complete one-line JSON printed above |

| Setup field | Value |
| --- | --- |
| MinerU cloud API token | Empty for Flash mode; otherwise your token |
| Output directory | `C:/mineru-out` |
| MCP transport | `stdio` |
| HTTP transport port | Ignored in stdio mode |

Flash-mode test using a non-confidential document:

> Parse pages 1-2 of `C:/absolute/path/public-test.pdf` using MinerU Flash mode.
> Return the Markdown headings, identify the called tool, and report any cloud
> URL or locally saved output path.

Remote-URL test:

> Parse the first two pages of this public PDF URL into Markdown. Preserve
> tables and formulas and list the exact MinerU tool called: `PUBLIC_PDF_URL`.

---

## 5. Minimal FastMCP wrapper: `mineru-fastmcp-wrapper`

Use this only when your self-hosted API exposes a synchronous multipart route
compatible with `/file_parse` or `/v1/file_parse`. MinerU 4.x's general
`/v1/tasks` API uses create, upload, poll, and download steps; for that API,
prefer `mineru-selfhosted-mcp` instead of expanding this lightweight wrapper.

Create an isolated environment:

```powershell
$WrapperRoot = Join-Path $ProjectRoot "mcp_tools\mineru-fastmcp-wrapper"
$WrapperVenv = Join-Path $WrapperRoot ".venv"
New-Item -ItemType Directory -Path $WrapperRoot -Force | Out-Null

py -m venv $WrapperVenv
$WrapperPython = Join-Path $WrapperVenv "Scripts\python.exe"
& $WrapperPython -m pip install --upgrade pip
& $WrapperPython -m pip install fastmcp httpx "pydantic==2.13.5"
```

If the wrapper environment was already created with Pydantic 2.14, repair it
before starting the server:

```powershell
& $WrapperPython -m pip install --upgrade "pydantic==2.13.5"
```

FastMCP 2.11.2 installs MCP SDK 1.10.1, which imports a Pydantic internal helper
removed in Pydantic 2.14. The 2.13.5 pin keeps that SDK importable.

Save the following as `mcp_tools/mineru-fastmcp-wrapper/server.py`:

```python
import io
import os
import zipfile
from pathlib import Path

import httpx
from fastmcp import FastMCP


mcp = FastMCP("MinerU local wrapper")


@mcp.tool
def parse_document(file_path: str) -> str:
    """Parse one local document through the configured MinerU endpoint."""
    source = Path(file_path).resolve(strict=True)
    base_url = os.environ["MINERU_BASE_URL"].rstrip("/")
    parse_path = os.getenv("MINERU_PARSE_PATH", "/file_parse")
    timeout = float(os.getenv("MINERU_TIMEOUT", "1800"))
    token = os.getenv("MINERU_API_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with source.open("rb") as document:
        response = httpx.post(
            f"{base_url}{parse_path}",
            headers=headers,
            files={"files": (source.name, document, "application/octet-stream")},
            timeout=timeout,
        )
    response.raise_for_status()
    if response.content.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            markdown_name = next(
                name for name in archive.namelist() if name.endswith(".md")
            )
            markdown = archive.read(markdown_name).decode("utf-8", "replace")
    else:
        payload = response.json()
        results = payload.get("results") or []
        markdown = results[0].get("md_content", "") if results else ""
    if not markdown.strip():
        raise RuntimeError("MinerU response did not contain Markdown")
    output_dir = Path(os.getenv("OUTPUT_DIR", "./mineru-out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.stem}.md"
    output_path.write_text(markdown, encoding="utf-8")
    return f"{markdown}\n\nSaved to: {output_path.resolve()}"


if __name__ == "__main__":
    mcp.run()
```

Start it once and press `Ctrl+C` after it reaches stdio wait state:

```powershell
$WrapperServer = Join-Path $WrapperRoot "server.py"
& $WrapperPython $WrapperServer
```

### CairnMark service values

| Field | Value |
| --- | --- |
| Name | `mineru-fastmcp-wrapper` |
| Timeout (ms) | `1800000` |
| Command | Absolute path stored in `$WrapperPython` |
| Args | JSON array containing the absolute `server.py` path |

Generate the Args field rather than typing escaped backslashes:

```powershell
ConvertTo-Json -InputObject @((Join-Path $WrapperRoot "server.py")) -Compress
```

| Setup field | Value |
| --- | --- |
| MinerU API base URL | `http://127.0.0.1:8000` |
| MinerU API token | Empty unless your service requires it |
| Synchronous parse route | Match your API: `/file_parse` or `/v1/file_parse` |
| Output directory | `C:/mineru-out` |
| API timeout | `1800` |

Wrapper test:

> Use `parse_document` on `C:/absolute/path/test.pdf`. Return the Markdown
> title, the first paragraph, and the absolute saved Markdown path.

---

## 6. Updating, secrets, and troubleshooting

- Setup fields prefixed internally with `env:` are passed only to the launched
  MCP process. Password-type fields are stored using CairnMark's encrypted
  secret handling and are not added to Args or displayed after saving.
- A timeout in CairnMark is measured in milliseconds. `1800000` corresponds to
  the packages' common 1800-second parsing timeout.
- `spawn ... ENOENT` means **Command** is not an absolute executable path.
- **Args must be a JSON array of strings** means the one-line JSON array is
  malformed or a PowerShell variable name was pasted instead of its output.
- A successful health check does not prove API compatibility. Check the
  installed MCP package's expected routes against your MinerU server version.
- If an offline uv launch fails, run the online cache command again, allow it
  to start, press `Ctrl+C`, and restore the `--offline` Args.
- After updating a package, select **Refresh** in MCP settings and review newly
  discovered tool names before enabling them.

Do not commit these generated locations:

| Location | Reason |
| --- | --- |
| `mcp_tools/mineru-*/` | Downloaded environments, caches, wrapper, and output |
| `services/custom_mcp.json` | Machine-specific commands and arguments |
| `instance/tools.db` | Local switches, encrypted setup values, and cached tools |
| `C:/mineru-out` | Parsed document content |

For global tool switches, quick automatic scope, execution limits, and service
refresh behavior, return to **[MCP tool handling](./mcp-tools.md)**.
