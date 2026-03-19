# comparePrice

Minimal Go CLI for the incubation stage. It accepts a prompt, sends it to OpenRouter using `openrouter/free`, prints the response, and writes a structured usage log for reporting.

## Requirements

- Go 1.22+
- An OpenRouter API key with credit available

## Setup

```bash
export OPENROUTER_API_KEY="your_api_key_here"
go run .
```

## Model

This project currently sends prompts to OpenRouter using the [free model](https://openrouter.ai/openrouter/free) alias:

```text
openrouter/free
```

## Usage

```text
Enter prompt (or type 'exit'): Summarize the cheapest grocery option for eggs.

Response:
...
```

Type `exit` to stop the program.

## Logging

Each successful request is appended to `logs/llm_logs.jsonl` with:

- timestamp
- provider
- model
- prompt
- response
- prompt tokens
- completion tokens
- total tokens
- latency in milliseconds

This log can be used later to build the required token and credit usage report.

## Planned Receipt Requirements

When receipt ingestion is added later, each receipt should include:

- `purchase_time`
- `store_name`
- `address`
- at least one visible item name with its cost
