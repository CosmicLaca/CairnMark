# Custom MCP tool examples

This guide configures four MCP services directly in CairnMark:

- the included Python weather example;
- the included Python stock-information example;
- a locally installed AntV Chart MCP server; and
- a locally installed LibreOffice MCP server.

These are **Custom** CairnMark services. They do not require llama.cpp MCP
configuration and this guide does not configure tools inside llama.cpp.

The repository can contain the example source code and package manifests, but
it intentionally does not contain the local MCP database, saved switches,
credentials, installed Node packages, or private `services/mcp.json`. Every
installation must add the services through the application and save its own
settings.

<!-- Screenshot placeholder: Custom MCP examples in the MCP settings modal. -->

---

## 1. Prepare CairnMark

Complete the normal CairnMark installation first. The commands below assume a
PowerShell terminal opened in the repository root:

```powershell
Set-Location "C:\path\to\CairnMark"
$ProjectRoot = (Get-Location).Path
```

The main Python environment already supplies the MCP Python package used by
`weather_server.py` and `stock_server.py`. Do not create separate virtual
environments for these two examples.

Open **Home**, select the tool icon below the chat input, and find **Add new
custom MCP service**. A local stdio service needs:

| Field | Purpose |
| --- | --- |
| Name | Unique service name shown in CairnMark |
| Timeout (ms) | Maximum startup, discovery, and call duration |
| Command | Absolute path to Python, Node.js, or another executable |
| Args (JSON array) | JSON array containing the server script and arguments |

The default endpoint, username, and password fields come from CairnMark's
fallback setup schema. Endpoint and username are not used by these four stdio
servers. Clear the endpoint when it is not needed. The stock example uses the
password field for its API key.

Select **Add tool** after entering a service. CairnMark starts the command,
performs MCP discovery, and adds the service only when it is reachable. Then:

1. enable the Custom parent service;
2. expand it and enable only the required subtools;
3. select **Save** in MCP settings; and
4. right-click the tool icon, enable global tool use, and save the global
   settings.

For document workflows, a useful starting configuration is 15 tool-call
rounds, 30 total calls, and two consecutive failures. Short weather and stock
requests normally need only one or two calls.

---

## 2. Weather example

### What it uses

`mcp_tools/weather_server.py` is a local Python stdio MCP server. It contacts
the public Open-Meteo geocoding and forecast APIs over HTTPS. It needs internet
access but does not require an API key.

It exposes:

| Tool | Purpose |
| --- | --- |
| `get_current_weather` | Current conditions for a named location |
| `get_weather_forecast` | A one-to-seven-day daily forecast |

Current weather supports Celsius or Fahrenheit and the `kmh`, `mph`, `ms`, and
`kn` wind-speed units. Forecast requests support one through seven days.

### Verify the files

```powershell
Test-Path .\mcp_tools\weather_server.py
Test-Path .\mcp_tools\http_client.py
```

Both commands should return `True`. No additional package installation is
needed after CairnMark's normal requirements are installed.

### Add the Custom service

Use these values:

| Field | Value |
| --- | --- |
| Name | `Weather` |
| Timeout (ms) | `15000` |
| Command | `<project>/venv/Scripts/python.exe` |
| Args | `["<project>/mcp_tools/weather_server.py"]` |

Generate the exact local values in PowerShell:

```powershell
$Python = (Resolve-Path .\venv\Scripts\python.exe).Path
$Weather = (Resolve-Path .\mcp_tools\weather_server.py).Path.Replace('\', '/')
$Python
"[`"$Weather`"]"
```

Paste the first output into **Command** and the JSON array into **Args**. Leave
endpoint, username, and password empty. Select **Add tool**, enable both weather
subtools, and save.

### Test prompts

> Use the Weather tool to report the current weather in Budapest, Hungary.
> Include observation time, temperature, apparent temperature, humidity,
> precipitation, wind speed, and source.

> Use the Weather forecast tool for a five-day forecast for London, United
> Kingdom. Return a Markdown table with date, conditions, minimum and maximum
> temperature, and maximum precipitation probability.

### Weather troubleshooting

- A place name can be ambiguous. Add the country or region to the prompt.
- `No location was found` means Open-Meteo geocoding returned no match.
- A reachability error usually indicates internet, DNS, proxy, or firewall
  trouble rather than an MCP configuration problem.
- The forecast `days` value must be between 1 and 7.

<!-- Screenshot placeholder: Weather Custom service and response. -->

---

## 3. Stock-information example

### What it uses

`mcp_tools/stock_server.py` is a local Python stdio MCP server backed by Alpha
Vantage. It requires internet access and an Alpha Vantage API key. Financial
data returned by this example is informational and is not investment advice.

It exposes:

| Tool | Purpose |
| --- | --- |
| `search_stock_symbols` | Find equity, ETF, or mutual-fund ticker symbols |
| `get_stock_quote` | Retrieve the latest end-of-day quote available |
| `get_daily_stock_prices` | Retrieve one through 100 recent daily OHLCV rows |

The free API tier can return delayed or end-of-day data and can enforce request
limits. CairnMark reports provider errors instead of silently inventing values.

### Verify the files

```powershell
Test-Path .\mcp_tools\stock_server.py
Test-Path .\mcp_tools\http_client.py
```

### Add the Custom service

Use these values:

| Field | Value |
| --- | --- |
| Name | `Stock` |
| Timeout (ms) | `15000` |
| Command | `<project>/venv/Scripts/python.exe` |
| Args | `["<project>/mcp_tools/stock_server.py"]` |
| Password | Your Alpha Vantage API key |

Generate the command and argument values:

```powershell
$Python = (Resolve-Path .\venv\Scripts\python.exe).Path
$Stock = (Resolve-Path .\mcp_tools\stock_server.py).Path.Replace('\', '/')
$Python
"[`"$Stock`"]"
```

Clear the endpoint and username fields. Put the API key only in **Password**.
CairnMark encrypts password fields in `instance/tools.db` and supplies this
value to the server process as `MCP_SERVICE_PASSWORD`; it is not placed in the
command, arguments, URL, or chat response.

Select **Add tool**, enable the parent service and the desired stock subtools,
then save.

### Test prompts

> Use the Stock tool to search for the ticker symbol of International Business
> Machines. Return symbol, company name, region, currency, and match score.

> Use the Stock tool to retrieve the latest available IBM quote. Include the
> trading date, open, high, low, price, previous close, change, change percent,
> volume, data freshness, and source.

> Use the Stock tool to retrieve the ten most recent daily prices for MSFT and
> present date, open, high, low, close, and volume in a table.

### Stock troubleshooting

- `An Alpha Vantage API key is required` means the password field is empty or
  was not saved.
- Provider `Information` or `Note` responses commonly indicate API limits.
- Search for a symbol before requesting a quote when the ticker is uncertain.
- Do not put the API key into the endpoint or prompt.

<!-- Screenshot placeholder: Stock Custom service and response. -->

---

## 4. AntV Chart MCP

### Install locally

The repository stores a pinned package manifest in `mcp_tools/antv-chart`.
`node_modules` is local installation data and is intentionally ignored by Git.
Node.js 18 or newer is required.

```powershell
node --version
npm --version
npm install --prefix .\mcp_tools\antv-chart --ignore-scripts
Test-Path .\mcp_tools\antv-chart\node_modules\@antv\mcp-server-chart\build\index.js
```

The final command should return `True`. The checked-in manifest currently pins
`@antv/mcp-server-chart` to version `0.9.10`.

### Add the Custom service

Use these values:

| Field | Value |
| --- | --- |
| Name | `AntV_Chart` |
| Timeout (ms) | `60000` |
| Command | Absolute path returned by `(Get-Command node).Source` |
| Args | Chart server path followed by `--transport`, `stdio` |

Generate values suitable for the form:

```powershell
$Node = (Get-Command node).Source
$AntV = (Resolve-Path .\mcp_tools\antv-chart\node_modules\@antv\mcp-server-chart\build\index.js).Path.Replace('\', '/')
$Node
"[`"$AntV`",`"--transport`",`"stdio`"]"
```

Leave endpoint, username, and password empty. Select **Add tool**, enable the
parent service, and enable only the chart generators you plan to use.

### Test prompts

> Use AntV Chart to create a line chart of monthly revenue: January 12000,
> February 14500, March 13200, April 17800, May 19300, June 22100. Title it
> “First Half Revenue”, label the Y axis “USD”, and return the generated chart.

> Use AntV Chart to create a dual-axis chart. Months: Jan, Feb, Mar, Apr, May.
> Sales: 120, 150, 135, 180, 210. Profit-margin percentages: 12, 15, 14, 18,
> 21. Use columns for sales and a line for profit margin.

### Chart responses and downloads

The MCP process runs locally, but a chart result can still be hosted at an
external image URL. CairnMark checks the response MIME type. When the URL is an
image—even when it has no filename extension—the assistant bubble displays an
image preview, reverse-image-search action, and download button.

If the remote host expires or blocks the URL later, a previously saved chat can
retain the link while the remote image itself is no longer available. Download
important chart images while they remain accessible.

### AntV troubleshooting

- If **Add tool** fails, verify the absolute Node and `build/index.js` paths.
- Rerun `npm install --prefix .\mcp_tools\antv-chart --ignore-scripts` after a
  fresh clone or deleted `node_modules` directory.
- A normal hyperlink instead of an image usually means the URL did not return
  an image MIME type or could not be reached.
- Enable only the chart subtools needed for the prompt to reduce model choice.

<!-- Screenshot placeholder: AntV Custom service and chart result. -->

---

## 5. LibreOffice MCP

### Requirements and local files

Install LibreOffice locally first. The integration uses LibreOffice's bundled
Python because that interpreter includes the required UNO bridge.

CairnMark's local integration consists of:

- `mcp_tools/libreoffice_server.py`, the CairnMark launcher;
- `mcp_tools/libreoffice-mcp/lo_mcp_server.py`, the MCP server;
- `mcp_tools/lo-profile-custom/`, generated local profile data; and
- `Generated-documents/`, generated document output.

The profile and generated documents are local data and are ignored by Git. The
included LibreOffice MCP server is Apache-2.0 licensed. No Docker container and
no separate Python package installation are required.

Verify the installation and locate LibreOffice's bundled Python. A common
Windows path is shown below; change it when LibreOffice is installed elsewhere:

```powershell
$LibreOfficePython = "C:\Program Files\LibreOffice\program\python.exe"
Test-Path $LibreOfficePython
Test-Path .\mcp_tools\libreoffice_server.py
Test-Path .\mcp_tools\libreoffice-mcp\lo_mcp_server.py
```

All three checks must return `True`.

### Add the Custom service

Use these values:

| Field | Value |
| --- | --- |
| Name | `LibreOffice` |
| Timeout (ms) | `120000` |
| Command | Absolute path to LibreOffice's `program/python.exe` |
| Args | `["<project>/mcp_tools/libreoffice_server.py"]` |

Generate the argument value:

```powershell
$Launcher = (Resolve-Path .\mcp_tools\libreoffice_server.py).Path.Replace('\', '/')
"[`"$Launcher`"]"
```

Leave endpoint, username, and password empty. Select **Add tool**. For Writer
document generation, enable at least:

- `lo_new`;
- `writer_append`;
- `writer_insert_table` when tables are required;
- `writer_list_styles` and `writer_set_paragraph` when paragraph styles are
  required;
- `lo_save`; and
- `lo_close`.

Enable Calc, Impress, Draw, conversion, image, or document-reading tools only
when a prompt needs them.

### Stateful document workflows

LibreOffice returns a document ID from `lo_new` or `lo_open`. CairnMark keeps
the Custom stdio MCP process alive for the complete assistant tool loop, so the
same document ID remains valid for append, table, save, and close calls. The
session closes after the assistant response. A prompt should therefore create,
edit, save, and close the document within one response.

The recommended 15 rounds and 30 total calls allow a model to perform a longer
Writer workflow. If execution stops before `lo_save`, check the global limits,
the consecutive-failure setting, and the assistant's tool-call transcript.

### Output, collision-safe names, and downloads

Relative save names are written inside `Generated-documents`. The launcher
restricts LibreOffice file access to that output directory.

LibreOffice save-as never overwrites an existing target. The first save keeps
the requested name. If that name already exists, the server appends local date
and time down to seconds:

```text
renewable-energy-outlook-2035-01.docx
renewable-energy-outlook-2035-01-2026-11-23_16-37-53.docx
```

A second collision in the same second receives an additional numeric suffix.
The tool result returns the actual path, and CairnMark renders that filename in
the assistant bubble as a document card with a download arrow.

Document cards are restored when an active chat is reloaded, a saved
conversation is resumed, or a CairnMark chat export is imported, provided the
referenced file still exists inside `Generated-documents`. Chat JSON does not
embed the document bytes. Copy `Generated-documents` separately when moving a
conversation to another installation.

### Writer test prompt

> Use LibreOffice tools to create a professionally formatted Writer document
> about renewable energy. Add the title “Renewable Energy Outlook 2035” using a
> title or heading style. Write substantial sections about solar power, wind
> energy, and energy storage. Insert a table with columns Technology, Typical
> Efficiency, Main Advantage, Main Challenge, and Outlook. Add a conclusion.
> Save the document as `renewable-energy-outlook-2035.docx`, then close it.

The current server supports paragraph styles and structured tables, but its
`writer_insert_table` tool does not expose granular cell background colors or
individual-cell bold formatting. The model should report unsupported styling
instead of claiming it was applied.

### LibreOffice troubleshooting

- `unknown doc_id` indicates that an older CairnMark process did not retain the
  Custom MCP session. Restart CairnMark after updating and repeat the complete
  prompt.
- No document card means `lo_save` did not complete, the returned path is
  outside `Generated-documents`, or the file was moved or deleted.
- A timestamped filename is expected when the requested target already exists.
- A port or profile conflict usually means another integration uses the same
  LibreOffice profile. CairnMark's launcher uses its own named pipe and
  `lo-profile-custom` directory.
- If LibreOffice is installed outside `C:\Program Files\LibreOffice`, use its
  actual bundled `program/python.exe` as the Custom service command and update
  the `LO_MCP_SOFFICE` default in `mcp_tools/libreoffice_server.py` when needed.

<!-- Screenshot placeholder: LibreOffice Custom service and document card. -->

---

## 6. Files that are local and private

Do not publish these runtime files as example configuration:

| Location | Why it remains local |
| --- | --- |
| `services/mcp.json` | Absolute commands, arguments, and private service declarations |
| `instance/tools.db` | Enabled states, cached schemas, settings, and encrypted passwords |
| `.secret/` | Encryption key required to decrypt saved credentials |
| `mcp_tools/*/node_modules/` | Reinstallable Node dependencies |
| `mcp_tools/lo-profile-custom/` | LibreOffice runtime profile |
| `Generated-documents/` | User-generated document files |

The reusable example code can be committed, including
`mcp_tools/weather_server.py`, `mcp_tools/stock_server.py`,
`mcp_tools/http_client.py`, the AntV package manifest and lock file, the
LibreOffice launcher, and the locally integrated LibreOffice MCP source and
license.

---

## 7. General troubleshooting

### The service is rejected by Add tool

- Use an absolute command path.
- Ensure **Args** is a valid JSON array of strings, not a PowerShell array or a
  plain command line.
- Use forward slashes inside JSON paths or escape each backslash.
- Run the `Test-Path` commands for the executable and server entry point.
- Increase the service timeout for slow LibreOffice startup.

### The service is online but the model does not use it

Confirm all three levels: global tool use, the Custom parent switch, and the
individual subtool switch. Use **Refresh** after installing a different package
version or changing exposed tools. Ask explicitly for the named tool in the
test prompt.

### Raw tool-call text appears in the assistant response

Use a model with reliable tool-call support. CairnMark can recover supported
llama.cpp raw-call templates, including multiline Writer text, but execution
still stops at the configured round, total-call, or failure limit.

### A saved or imported chat has no download

CairnMark reconstructs document cards from verified LibreOffice save results.
The referenced file must still exist in `Generated-documents`; the conversation
record alone is not a document backup.

For the global switch, execution policy, service states, and refresh behavior,
return to **[MCP tool handling](./mcp-tools.md)**. For SearXNG, use the separate
**[local SearXNG setup guide](./tool-setup.md)**.
