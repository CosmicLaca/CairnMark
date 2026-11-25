Create one benchmark question and its reference answer for the category, topic, and difficulty level defined in the user message.
Prompts (questions) and their reference answers must not be too long; they should be of easy-to-moderate difficulty. If the topic is subjective or creative, the response should be one possible good answer. In scientific topics such as math, the year of an event, numerical or programming-related requests, the response must be the only exact value or exact answer.
All API responses must contain only the raw answer: no comments, no text that suggests or thinks about the answer, no additional questions or ideas. Just the finished raw answer.

## Output format

| Key | JSON type        | Meaning                                                                      |
|---|------------------|------------------------------------------------------------------------------|
| `benchmarks` | list             | The list of 1 benchmark reference data.                                      |
| `request` | string           | The question prompt. It must be self-contained and unambiguous.              |
| `response` | string           | One good reference answer.                                                   |
| `answer_type` | string           | Exactly one of `"exact"`, `"numeric"`, `"open"`.                             |
| `accepted_answers` | array of strings | Other correct ways to write the same answer. `[]` if none or not applicable. |
| `numeric_tolerance` | number or `null` | Maximum allowed relative error. Only for `"numeric"`, otherwise `null`.      |
| `key_points` | array of strings | Statements a correct answer must contain. Only for `"open"`, otherwise `[]`. |


Return only one valid JSON object. Do not return markdown, explanations, an array, a topic key, or a `benchmarks` key. Use exactly these six keys:

```json
{
  "request": "self-contained question",
  "response": "reference answer",
  "answer_type": "exact | numeric | open",
  "accepted_answers": [],
  "numeric_tolerance": null,
  "key_points": []
}
```

## Answer types

- `exact`: one correct value, name, term, date, formula, count, or program output. Ask for a single answer. Make `response` the shortest correct form. Put up to six equivalent spellings or forms in `accepted_answers`. Use `numeric_tolerance: null` and `key_points: []`.
- `numeric`: a measured, approximate, or rounded number. State units and precision when needed. Use a numeric relative tolerance from `0.001` to `0.05` (`0.01` means 1%). Equivalent values may go in `accepted_answers`. Use `key_points: []`.
- `open`: an explanation, definition, comparison, opinion, or creative answer. Write a good response in one to three short sentences. Use two to five non-overlapping required claims in `key_points`. Use `accepted_answers: []` and `numeric_tolerance: null`.

Never use `open` for a value, name, date, calculation, or count. Use `open` when the question asks to explain, describe, compare, why, or how.

Use double quotes and valid JSON. `request` and `response` are strings. `accepted_answers` and `key_points` are arrays of strings. `numeric_tolerance` is a JSON number or `null`, never a string. Do not omit or add keys.

## Exact example — never reuse its content

```json
{
  "request": "How many sides does a hexagon have?",
  "response": "6",
  "answer_type": "exact",
  "accepted_answers": ["six", "6 sides"],
  "numeric_tolerance": null,
  "key_points": []
}
```

## Numeric example — never reuse its content

```json
{
  "request": "What is the approximate speed of light in vacuum in km/s?",
  "response": "299792 km/s",
  "answer_type": "numeric",
  "accepted_answers": ["300000 km/s", "2.998e5 km/s"],
  "numeric_tolerance": 0.01,
  "key_points": []
}
```

## Open example — never reuse its content

```json
{
  "request": "Why does the sky look blue during the day?",
  "response": "Air molecules scatter short blue wavelengths of sunlight more strongly than longer red wavelengths, so blue light reaches our eyes from across the sky.",
  "answer_type": "open",
  "accepted_answers": [],
  "numeric_tolerance": null,
  "key_points": [
    "Air molecules scatter sunlight.",
    "Shorter blue wavelengths scatter more strongly than longer red wavelengths.",
    "Scattered blue light reaches the eye from across the sky."
  ]
}
```
