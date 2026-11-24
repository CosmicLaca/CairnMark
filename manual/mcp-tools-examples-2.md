# Custom MCP tool examples: Wikipedia and Yahoo Finance

This guide installs and configures three key-free MCP services directly in
CairnMark:

- Wikipedia MCP for article search, summaries, sections, links, key facts, and
  related topics;
- `yfmcp`, the feature-rich Yahoo Finance server; and
- `yahoo-finance-mcp-server`, a smaller alternative Yahoo Finance server.

These are **Custom** CairnMark services. The instructions do not add them to
OpenCode or llama.cpp. Their setup schemas are committed to the repository,
but their installed packages, uv caches, private `services/mcp.json`, and
`instance/tools.db` records are local data and must be recreated after a fresh
clone.

Wikipedia does not require an API key. Both finance servers use unofficial
Yahoo Finance endpoints through `yfinance`; Yahoo's terms, availability, data
delay, and request limits apply. Their output is informational and is not
financial advice.

---

## 1. Prepare CairnMark

Complete the normal CairnMark installation first. Open PowerShell in the
repository root and keep the absolute project path for the commands below:

```powershell
Set-Location "C:\path\to\CairnMark"
$ProjectRoot = (Get-Location).Path
```

Open **Home**, select the tool icon below the chat input, and use **Add new
custom MCP service** for each server. After a service is accepted:

1. enable its Custom parent switch;
2. expand it and enable the required subtools;
3. select **Save** in MCP settings;
4. right-click the tool icon, enable global tool use, and save; and
5. use **Refresh** only after installing a version that changes its tool list.

The first discovery may take longer because pipx or uv creates an isolated
Python environment. Always use an absolute executable path and a valid JSON
array in **Args**.

---

## 2. Wikipedia MCP

### Features and source

[Wikipedia MCP](https://github.com/Rudra-ravi/wikipedia-mcp) exposes Wikipedia
search, full articles, summaries, sections, links, coordinates, key facts, and
related topics. The server supports multiple Wikipedia languages and optional
response caching.

### Install Python and pipx

Wikipedia MCP is installed into `mcp_tools/wikipedia-mcp`, not into CairnMark's
main virtual environment. Python 3.11 or newer and pipx are required. If `pipx`
is not already installed, run:

```powershell
py -m pip --version
py -m pip install --user pipx
py -m pipx ensurepath
```

`ensurepath` may ask you to restart PowerShell. The commands below use
`py -m pipx`, so they also work before the restarted shell finds `pipx.exe`.

Create an application-local pipx home and install the server:

```powershell
$WikipediaRoot = Join-Path $ProjectRoot "mcp_tools\wikipedia-mcp"
$env:PIPX_HOME = $WikipediaRoot
$env:PIPX_BIN_DIR = Join-Path $WikipediaRoot "bin"
$env:PIPX_MAN_DIR = Join-Path $WikipediaRoot "man"
$env:PIPX_SHARED_LIBS = Join-Path $WikipediaRoot "shared"

py -m pipx install wikipedia-mcp

$WikipediaCommand = (
    Resolve-Path (Join-Path $env:PIPX_BIN_DIR "wikipedia-mcp.exe")
).Path
$WikipediaCommand
Test-Path $WikipediaCommand
```

The final check must return `True`. Keep the four `PIPX_*` variables set when
running `py -m pipx upgrade wikipedia-mcp` or uninstalling this local copy.

### Add the Custom service

Use these values:

| Field | Value |
| --- | --- |
| Name | `Wikipedia` |
| Timeout (ms) | `30000` |
| Command | Value printed as `$WikipediaCommand` |
| Args | `[]` |

Leave endpoint, username, and password empty. Do not hard-code `--language` or
`--enable-cache` in **Args**. The committed
`static/tool-setup-wikipedia.json` schema provides:

- a language selector with English as the default; and
- an **Enable response cache** switch, on by default.

CairnMark converts those two saved fields into the server's `--language` and
`--enable-cache` command arguments. Changing the language therefore requires
only **Set up** → choose the language → **Save**.

The upstream server publishes each operation under a short name and a second
`wikipedia_`-prefixed alias. They are equivalent public MCP tools, not leaked
internal functions. Enable one set only. The shorter names are normally easier
for a model to select, so leave the prefixed aliases disabled.

### Wikipedia test prompts

> Use only the Wikipedia MCP tools—do not use SearXNG or prior knowledge.
> Search for “Budapest”, retrieve its summary, extract five key facts, and
> suggest three related Wikipedia topics. Answer in English and list the exact
> tools you called.

<!-- Add the Wikipedia result screenshot here. -->

Change the setup language to Hungarian, save it, and try:

> Kizárólag a Wikipedia MCP eszközeit használd. Keress rá Bartók Béla nevére,
> foglald össze a szócikket magyarul, sorolj fel öt fontos tényt, majd adj meg
> három kapcsolódó témát. A végén nevezd meg a használt eszközöket.

### Wikipedia troubleshooting

- `spawn ... ENOENT` or an offline service usually means **Command** is not the
  absolute path to `mcp_tools/wikipedia-mcp/bin/wikipedia-mcp.exe`.
- An empty or invalid **Args** value must be corrected to the JSON array `[]`.
- If the response comes from the wrong Wikipedia edition, reopen **Set up**,
  confirm the language, and save the service settings.
- Article titles can be ambiguous. Search first, then pass an exact returned
  title to summary or article tools.
- Keep only one of each short/prefixed alias pair enabled.

---

## 3. Install uv for the Yahoo Finance servers

Both Yahoo Finance servers use `uvx`. Check the existing installation:

```powershell
uv --version
uvx --version
```

If either command is missing, install uv with Windows Package Manager:

```powershell
winget install --id=astral-sh.uv -e
```

Close and reopen PowerShell after installation, return to the repository root,
and recreate `$ProjectRoot`. Then locate the absolute runner path:

```powershell
$Uvx = (Get-Command uvx).Source
$Uvx
```

The following sections place each package cache in its own `mcp_tools`
subfolder. These caches are intentionally not committed.

---

## 4. yfmcp

### Features and local installation

[`yfmcp`](https://github.com/narumiruna/yfinance-mcp) exposes ticker search,
company information, price history, news, financial statements, fund data,
holders, options, analyst data, sector leaders, and screeners.

Create the local cache and pre-download the current release:

```powershell
$YfmcpCache = Join-Path $ProjectRoot "mcp_tools\yfmcp\cache"
New-Item -ItemType Directory -Path $YfmcpCache -Force | Out-Null

& $Uvx --isolated --cache-dir $YfmcpCache "yfmcp@latest"
```

The last command starts the stdio MCP server and waits for a client. After the
download finishes and the server starts, press `Ctrl+C`. This is expected and
does not remove the cached installation.

Generate the exact JSON argument array for CairnMark:

```powershell
$YfmcpArgs = @(
    "--offline",
    "--isolated",
    "--cache-dir",
    $YfmcpCache,
    "yfmcp@latest"
)
ConvertTo-Json -InputObject $YfmcpArgs -Compress
```

### Add the Custom service

| Field | Value |
| --- | --- |
| Name | `yfmcp` |
| Timeout (ms) | `120000` |
| Command | Value printed as `$Uvx` |
| Args | JSON printed from `$YfmcpArgs` |

Leave endpoint, username, and password empty. The `--offline` argument makes
normal CairnMark launches use the local cache instead of checking PyPI every
time.

The committed `static/tool-setup-yfmcp.json` schema provides defaults for:

- history period and price interval;
- inclusion of pre-market and post-market data;
- annual, quarterly, or trailing-12-month financials;
- calls, puts, or both option types;
- quote/news search type;
- sector top-result count; and
- screener region.

These are tool-call defaults, not uvx launch arguments. CairnMark supplies a
saved value only to tools whose MCP input schema supports that field. An
argument explicitly chosen by the model for the current request takes priority.

### yfmcp test prompts

> Use only the `yfmcp` tools. Find Toyota's US ticker, retrieve its company
> information, latest news, and five-day daily price history. Present the
> prices in a Markdown table and list every tool called.

<!-- Add the yfmcp search and history result screenshot here. -->

> Use only `yfmcp`. Retrieve AAPL option expiration dates, select the nearest
> available date, and summarize both calls and puts for that date. Clearly show
> the expiration date and identify the tools used.

> Use only `yfmcp`. Show the ten largest Technology-sector companies and then
> retrieve detailed ticker information for the first company. State that the
> Yahoo Finance source is unofficial.

### yfmcp troubleshooting

- If **Add tool** times out during the first start, verify that the pre-download
  completed and keep the timeout at `120000`.
- An offline uv error means the cache is incomplete. Remove `--offline`
  temporarily, start once successfully, then restore it.
- Intraday intervals require short compatible periods. For example, a
  one-minute interval cannot retrieve many months of history.
- Ticker search can return different regional listings. Include the exchange or
  country when the company has several symbols.
- Enable only the tools needed for the workflow when the model struggles to
  choose among all available finance operations.

---

## 5. yahoo-finance-mcp-server

### Features and local installation

[`yahoo-finance-mcp-server`](https://github.com/laxmimerit/yahoo-finance-mcp-server)
is a smaller alternative exposing stock information, historical prices, news,
corporate actions, statements, holders, option dates and chains, and analyst
recommendations.

Create and warm its separate cache:

```powershell
$YahooServerCache = Join-Path $ProjectRoot "mcp_tools\yahoo-finance-mcp-server\cache"
New-Item -ItemType Directory -Path $YahooServerCache -Force | Out-Null

& $Uvx --isolated --cache-dir $YahooServerCache "yahoo-finance-mcp-server"
```

After the server reports that it has started, press `Ctrl+C`. Generate the form
arguments:

```powershell
$YahooServerArgs = @(
    "--offline",
    "--isolated",
    "--cache-dir",
    $YahooServerCache,
    "yahoo-finance-mcp-server"
)
ConvertTo-Json -InputObject $YahooServerArgs -Compress
```

### Add the Custom service

| Field | Value |
| --- | --- |
| Name | `yahoo-finance-mcp-server` |
| Timeout (ms) | `120000` |
| Command | Value printed as `$Uvx` |
| Args | JSON printed from `$YahooServerArgs` |

Leave endpoint, username, and password empty. The committed
`static/tool-setup-yahoo-finance-mcp-server.json` schema provides defaults for:

- history period and interval;
- annual or quarterly income, balance-sheet, and cash-flow statements;
- holder information type;
- call or put options;
- recommendations or upgrades/downgrades; and
- recommendation history in months.

As with `yfmcp`, these defaults are added only when a called tool supports the
field and the model did not already provide a value.

### Alternative-server test prompts

> Use only `yahoo-finance-mcp-server`. For MSFT, retrieve stock information,
> one-month daily history, recent news, corporate actions, and analyst
> recommendations from the last six months. List every tool called.

<!-- Add the alternative Yahoo Finance result screenshot here. -->

> Use only `yahoo-finance-mcp-server`. Retrieve NVIDIA's quarterly income
> statement and institutional holders. Summarize the important values without
> presenting them as investment advice.

> Use only `yahoo-finance-mcp-server`. Find the available SPY option expiration
> dates, select the nearest date, and retrieve its call option chain. State the
> selected expiration date and the exact tools used.

### Alternative-server troubleshooting

- Use the exact service name so CairnMark loads the matching setup schema.
- When an option-chain request fails, retrieve valid expiration dates first.
- Some statements, holder categories, recommendations, or options are not
  available for every ticker.
- Intraday Yahoo history is limited and may be delayed or rate-limited.

---

## 6. Compare the two Yahoo Finance servers

The services overlap because both use `yfinance`, but their MCP interfaces are
different. `yfmcp` is broader and includes ticker search, funds, screeners, and
more detailed analyst operations. `yahoo-finance-mcp-server` is smaller and can
be easier for a model to navigate.

For normal chat, enable only one finance service to reduce tool ambiguity. Keep
both enabled when comparing schemas, checking whether one server handles a
ticker better, or demonstrating equivalent sources.

Comparison prompt:

> Query both Custom Yahoo Finance MCP services for AAPL company information
> and one-month daily price history. Compare their returned values, clearly
> label which service supplied each result, report any differences, and list
> every tool called. Do not provide investment advice.

<!-- Add the side-by-side Yahoo Finance result screenshot here. -->

The two responses can differ because they may select different `yfinance`
fields, formatting, dependency versions, or request times. Agreement between
the two wrappers is not independent confirmation because both ultimately use
Yahoo Finance.

---

## 7. Updating the local installations

Upgrade Wikipedia with the same application-local pipx variables used during
installation:

```powershell
$WikipediaRoot = Join-Path $ProjectRoot "mcp_tools\wikipedia-mcp"
$env:PIPX_HOME = $WikipediaRoot
$env:PIPX_BIN_DIR = Join-Path $WikipediaRoot "bin"
$env:PIPX_MAN_DIR = Join-Path $WikipediaRoot "man"
$env:PIPX_SHARED_LIBS = Join-Path $WikipediaRoot "shared"
py -m pipx upgrade wikipedia-mcp
```

Refresh either uv cache by rerunning its online warm-up command with
`--refresh`, then pressing `Ctrl+C` after startup:

```powershell
& $Uvx --refresh --isolated --cache-dir $YfmcpCache "yfmcp@latest"
& $Uvx --refresh --isolated --cache-dir $YahooServerCache "yahoo-finance-mcp-server"
```

After any upgrade, open MCP settings and select **Refresh**. Review newly added
or renamed tools before enabling them. A schema committed with CairnMark may
also need updating if an upstream server changes accepted argument values.

---

## 8. Files to commit and files to keep local

Commit the reusable integration files:

- `static/tool-setup-wikipedia.json`;
- `static/tool-setup-yfmcp.json`;
- `static/tool-setup-yahoo-finance-mcp-server.json`; and
- this manual page and its navigation links.

Do not commit the recreated runtime data:

| Location | Reason |
| --- | --- |
| `mcp_tools/wikipedia-mcp/` | pipx environment and generated launchers |
| `mcp_tools/yfmcp/cache/` | downloaded uv packages and environments |
| `mcp_tools/yahoo-finance-mcp-server/cache/` | downloaded uv packages and environments |
| `services/mcp.json` | machine-specific absolute commands and arguments |
| `instance/tools.db` | local switches, cached definitions, and settings |

For global switches, execution limits, service status, refresh behavior, and
general troubleshooting, return to **[MCP tool handling](./mcp-tools.md)**.
The first group of local examples remains in
**[Custom MCP tool examples](./mcp-tools-examples.md)**.
