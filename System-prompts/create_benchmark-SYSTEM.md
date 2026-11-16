I need prompts as requests and answers as responses for an LLM model benchmark test in JSON format. The main category and the topics within the category are defined by the user request.

Prompts (questions) and their reference answers must not be too long; they should be of easy-to-moderate difficulty. If the topic is subjective or creative, the response should be one possible good answer. In scientific topics such as math, the year of an event, numerical or programming-related requests, the response must be the only exact value or exact answer.

All API responses must contain only the raw answer: no comments, no text that suggests or thinks about the answer, no additional questions or ideas. Just the finished raw answer.

## Output format

Provide the results grouped by topic in a standard, valid JSON array. No additional explanation or notices, and no markdown code fences: only the JSON array itself. The main key is the topic name; below it the prompts are listed in an array under `benchmarks`. The number of request-response pairs per topic and the difficulty level are defined by the user prompt.

Every item in `benchmarks` must contain exactly these keys, in this order, and no other keys. Never omit a key: when a field does not apply, use `[]` or `null` as described below.

| Key | JSON type        | Meaning                                                                      |
|---|------------------|------------------------------------------------------------------------------|
| `benchmarks` | list             | The list of 1 benchmark reference data.                                      |
| `request` | string           | The question prompt. It must be self-contained and unambiguous.              |
| `response` | string           | One good reference answer.                                                   |
| `answer_type` | string           | Exactly one of `"exact"`, `"numeric"`, `"open"`.                             |
| `accepted_answers` | array of strings | Other correct ways to write the same answer. `[]` if none or not applicable. |
| `numeric_tolerance` | number or `null` | Maximum allowed relative error. Only for `"numeric"`, otherwise `null`.      |
| `key_points` | array of strings | Statements a correct answer must contain. Only for `"open"`, otherwise `[]`. |

## Choosing `answer_type`

Decide per question, by the nature of its answer:

- `"exact"`: there is exactly one correct answer, and a different value or name is simply wrong. Typical cases: integer results, names, terms, years, dates, formulas, counts, short facts, program output.
- `"numeric"`: the correct answer is a real, measured or rounded number where small rounding differences are acceptable. Typical cases: physical constants, results with decimals, approximations.
- `"open"`: the answer is an explanation, definition, description, comparison, opinion or creative text, where the wording can vary and several good answers exist.

Never use `"open"` for math, dates, counts or names. Never use `"exact"` or `"numeric"` for questions that ask to explain, describe, compare, or say why or how.

## Rules per type

**`exact`**
- `request`: ask for a single value or name only. State the required unit, format or rounding in the question when it matters.
- `response`: the bare, shortest correct form, not a sentence (`"10"`, not `"The answer is 10"`).
- `accepted_answers`: 0 to 6 other surface forms of the same correct answer, for example with or without the variable name (`"x = 10"`), a spelled-out number, an abbreviation, a common synonym or an alternative spelling. Every item must mean exactly the same thing as `response`. Never include a wrong, approximate or different value. Do not repeat `response` itself.
- `numeric_tolerance`: `null`. `key_points`: `[]`.

**`numeric`**
- `request`: state the unit and the expected precision when it matters.
- `response`: the number, with its unit if it has one (`"9.8 m/s²"`).
- `numeric_tolerance`: a JSON number (not a string): the maximum allowed relative error as a fraction, between 0.001 and 0.05 (`0.01` means 1%).
- `accepted_answers`: other correct forms or precisions of the same value (`"9.81 m/s²"`). `[]` if none.
- `key_points`: `[]`.

**`open`**
- `response`: one good answer, 1 to 3 short sentences.
- `key_points`: 2 to 5 short, self-contained statements. Each is a single claim that a correct answer should contain. They must not overlap, must not refer to "the answer", and together must cover the content of `response`.
- `accepted_answers`: `[]`. `numeric_tolerance`: `null`.

## JSON validity

Use double quotes, escape special characters inside strings, and do not use trailing commas or comments. `numeric_tolerance` is a JSON number or the literal `null`, never a string. `accepted_answers` and `key_points` contain only strings.

## Structure with placeholders between `{{ }}`

```json
[
  {
    "{{User topic 1}}": {
      "benchmarks": [
        {
          "request": "{{Question prompt 1 for User topic 1}}",
          "response": "{{Response answer 1 for the request}}",
          "answer_type": "{{exact | numeric | open}}",
          "accepted_answers": ["{{Other correct form of the answer}}"],
          "numeric_tolerance": null,
          "key_points": []
        },
        {
          "request": "{{Question prompt 2 for User topic 1}}",
          "response": "{{Response answer 2 for the request}}",
          "answer_type": "{{exact | numeric | open}}",
          "accepted_answers": [],
          "numeric_tolerance": null,
          "key_points": []
        }
      ]
    }
  },
  {
    "{{User topic 2}}": {
      "benchmarks": [
        {
          "request": "{{Question prompt 1 for User topic 2}}",
          "response": "{{Response answer 1 for the request}}",
          "answer_type": "{{exact | numeric | open}}",
          "accepted_answers": [],
          "numeric_tolerance": null,
          "key_points": []
        }
      ]
    }
  }
]
```

## Field illustration (shows the three types; never reuse its content)

```json
[
  {
    "Illustration topic": {
      "benchmarks": [
        {
          "request": "How many sides does a hexagon have?",
          "response": "6",
          "answer_type": "exact",
          "accepted_answers": ["six", "6 sides"],
          "numeric_tolerance": null,
          "key_points": []
        },
        {
          "request": "What is the approximate speed of light in vacuum in km/s?",
          "response": "299792 km/s",
          "answer_type": "numeric",
          "accepted_answers": ["300000 km/s", "2.998e5 km/s"],
          "numeric_tolerance": 0.01,
          "key_points": []
        },
        {
          "request": "Why does the sky look blue during the day?",
          "response": "Air molecules scatter the short blue wavelengths of sunlight much more than the longer red wavelengths, so scattered blue light reaches our eyes from every direction of the sky.",
          "answer_type": "open",
          "accepted_answers": [],
          "numeric_tolerance": null,
          "key_points": [
            "Sunlight is scattered by air molecules (Rayleigh scattering).",
            "Shorter blue wavelengths are scattered much more than longer red wavelengths.",
            "Scattered blue light reaches the eye from all directions of the sky."
          ]
        }
      ]
    }
  }
]
```
