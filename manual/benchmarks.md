# Benchmark workflow

CairnMark stores benchmark prompt sets as user-owned JSON files. The workflow is
split into creation, organization, preview/editing, and execution.

## Create benchmark JSON

<!-- Screenshot placeholder: replace manual/create-benchmark.jpg when needed. -->
<p align="left"><img src="create-benchmark.jpg" width="82%" alt="Create benchmark page"></p>

1. Choose an existing category or create a new one.
2. Select Easy, Normal, or Hard.
3. Choose an enabled model.
4. Add one or more topics and request-response pair counts.
5. Review the system and user prompt templates.
6. Generate the file.

Generation progress follows topics as the model streams JSON. CairnMark extracts
the first valid JSON value, writes it atomically to `Benchmark-prompts/`, and
saves category, difficulty, generation prompt, and model metadata in
`instance/cairnmark.db`.

The default prompt templates are:

- `System-prompts/create_benchmark-SYSTEM.md`; and
- `System-prompts/create_benchmark-USER.md`.

## Browse and edit files

<!-- Screenshot placeholder: replace manual/view-benchmark.jpg when needed. -->
<p align="left"><img src="view-benchmark.jpg" width="82%" alt="Benchmark browser and preview"></p>

The Run benchmark page discovers `.json` files directly inside
`Benchmark-prompts/`. Categories and difficulty filters come from saved
metadata. A preview shows topics, requests, expected responses, and recorded
answers without executing a model.

Select a file to edit its category, difficulty, notes, generation prompt, and
model name. Creating a category before any benchmark uses it stores that name in
the database; category matching is case-insensitive.

## Run a benchmark

<!-- Screenshot placeholder: replace manual/run-benchmark.jpg when needed. -->
<p align="left"><img src="run-benchmark.jpg" width="82%" alt="Run benchmark page"></p>

1. Select a benchmark file.
2. Choose an enabled model.
3. Review the system prompt.
4. Optionally enable Markdown logging.
5. Start the run.

Each request sends only its `request` value to the model. The expected
`response`, evaluation fields, and every other JSON key stay local. CairnMark
records the model answer and response time in that request's `answers` array.

The file is replaced atomically in its original directory. Unknown keys such as
`answer_type` are preserved. Optional logs are written to
`Benchmark-prompts/logs/`.

## File expectations

- Files must use the `.json` extension.
- Files must be directly inside `Benchmark-prompts/`.
- The JSON must use supported nested topic/request structures.
- The browser treats file content and model output as untrusted text.

If a file is missing, validate its extension and JSON syntax, then reload the
page. CairnMark never scans arbitrary directories for benchmark data.

## Current limits

Automated evaluation, benchmark result history, result export, and accounts are
not working features in the preview. The evaluation page remains development
only and should not be treated as a completed workflow.
