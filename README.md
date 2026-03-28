# comparePrice

Minimal Go CLI for the incubation stage. It accepts a prompt, sends it to OpenRouter or CLOD, prints the response, and writes a structured usage log for reporting.

## Requirements

- Go 1.22+
- An OpenRouter API key with credit available, or a CLOD API key

## Setup

```bash
export LLM_PROVIDER="openrouter"
export OPENROUTER_API_KEY="your_api_key_here"
export OPENROUTER_MODEL="qwen/qwen3-235b-a22b-2507"
export OPENROUTER_FALLBACK_MODEL="deepseek/deepseek-chat-v3-0324:free"
go run .
```

```bash
export LLM_PROVIDER="clod"
export CLOD_API_KEY="your_api_key_here"
export CLOD_MODEL="Qwen 3 235B A22B Instruct 2507 TPUT"
export CLOD_FALLBACK_MODEL="Llama 3.1 8B"
go run .
```

```bash
export LLM_PROVIDER="both"
export OPENROUTER_API_KEY="your_openrouter_api_key"
export CLOD_API_KEY="your_clod_api_key"
go run .
```

To run the app with debug logging enabled:

```bash
export LLM_PROVIDER="clod"
export CLOD_API_KEY="your_api_key_here"
export CLOD_MODEL="Qwen 3 235B A22B Instruct 2507 TPUT"
export LOG_LEVEL="DEBUG"
go run .
```

## Provider Selection

This project reads `LLM_PROVIDER` to decide which backend to call.

- `openrouter` is the default when `LLM_PROVIDER` is unset
- `clod` uses CLOD's OpenAI-compatible endpoint at `https://api.clod.io/v1/chat/completions`
- `both` sends the same prompt to both CLOD and OpenRouter, then prints a side-by-side comparison

## API References

The current CLOD integration was implemented from their public docs:

- CLOD API docs: `https://clod.io/docs`
- Documented base URL: `https://api.clod.io`
- Documented chat endpoint: `/v1/chat/completions`
- Documented auth format: `Authorization: Bearer <API_KEY>`

The docs also describe CLOD as OpenAI-compatible and show example request fields such as `model`, `messages`, `temperature`, and `max_completion_tokens`.

For OpenRouter, the code continues to use their chat completions endpoint:

- OpenRouter API endpoint used in code: `https://openrouter.ai/api/v1/chat/completions`

Note: `CLOD_MODEL="Qwen 3 235B A22B Instruct 2507 TPUT"` is the current project default chosen for this comparison setup. You can still override it with any CLOD-supported model.

## Model

For OpenRouter, the project reads the model from `OPENROUTER_MODEL`.

If that variable is not set, it defaults to:

```text
qwen/qwen3-235b-a22b-2507
```

For CLOD, the project reads the model from `CLOD_MODEL`.

If that variable is not set, it defaults to:

```text
Qwen 3 235B A22B Instruct 2507 TPUT
```

## Guardrails

The CLI now sends a default system prompt that keeps the chatbot focused on:

- grocery products
- prices
- receipts
- store comparisons
- shopping recommendations
- checking retrieved receipts for cheaper or clearly similar items
- saying the user's price is the best confirmed price so far when no record exists

You can override the default behavior by setting either:

```bash
export OPENROUTER_SYSTEM_PROMPT="your custom system prompt"
export CLOD_SYSTEM_PROMPT="your custom system prompt"
```

If the primary model returns `429`, the CLI retries automatically with short backoff. You can also configure a fallback model with:

```bash
export OPENROUTER_FALLBACK_MODEL="deepseek/deepseek-chat-v3-0324:free"
export CLOD_FALLBACK_MODEL="Llama 3.1 8B"
```

When set, the CLI will try that fallback model after repeated `429` failures from the primary model.

## Current Analysis Flow

Today, the price-comparison analysis is performed by the LLM itself.

The Go app currently sends:

- a system prompt with shopping and receipt-comparison instructions
- all JSON receipt files found in `output/`
- the user's prompt

The model then decides whether a cheaper price or a clearly similar cheaper item exists based on the receipt data included in the prompt/context it receives.

## Usage

```text
Do you have a receipt to scan? (yes/no or type 'exit'): no
Enter prompt (or type 'exit'): Summarize the cheapest grocery option for eggs.

Response:
...
```

If the user selects `yes`, the current CLI shows a placeholder message explaining that live receipt scanning is not supported yet and asks the user to place receipt JSON in `output/` for now.

Type `exit` at either prompt to stop the program.

When `LLM_PROVIDER="both"`, the CLI prints:

- the CLOD response
- the OpenRouter response
- comparison of `llm_latency_ms`
- comparison of `llm_input_tokens`
- comparison of `llm_output_tokens`
- comparison of `llm_success`

## Red-Team Prompts

`redteam_prompts.txt` includes example malicious or out-of-scope prompts for checking whether the chatbot:

- refuses attempts to become a coding bot
- refuses hidden prompt extraction
- avoids hallucinating unsupported prices or receipt data
- stays in the compare-price assistant role

## Logging

Each successful request is appended to `logs/llm_logs.json` with:

- `llm_provider`
- `llm_latency_ms`
- `llm_input_tokens`
- `llm_output_tokens`
- `llm_success`
- `context` only when `LOG_LEVEL=DEBUG`

This log can be used later to build the required token and credit usage report.

When `LLM_PROVIDER="both"`, the app writes two log entries per prompt, one for CLOD and one for OpenRouter.

Example:

```json
{
  "llm_provider": "Qwen 3 235B A22B Instruct 2507 TPUT",
  "llm_latency_ms": 2100,
  "llm_input_tokens": 800,
  "llm_output_tokens": 200,
  "llm_success": true
}
```

To include the optional debug context:

```bash
export LOG_LEVEL="DEBUG"
```

Full example:

```bash
export LLM_PROVIDER="openrouter"
export OPENROUTER_API_KEY="your_api_key_here"
export OPENROUTER_MODEL="qwen/qwen3-235b-a22b-2507"
export LOG_LEVEL="DEBUG"
go run .
```

## Railtracks

If you want the Railtracks dashboard to show a provider comparison for the real Go app, use the wrapper script in [railtracks_compareprice.py]
Install Railtracks with CLI support:

```bash
python -m pip install "railtracks[cli]"
```

Terminal 1: start the Railtracks dashboard

```bash

railtracks viz
```

Terminal 2: run the Railtracks wrapper that calls `go run .` once for CLOD and once for OpenRouter

```bash
export CLOD_API_KEY="your_api_key_here"
export OPENROUTER_API_KEY="your_api_key_here"
python railtracks_compareprice.py
```

The wrapper sends the same prompt into the Go CLI twice, once with `LLM_PROVIDER="clod"` and once with `LLM_PROVIDER="openrouter"`. Railtracks records separate tracked nodes for:

- `run_clod`
- `run_openrouter`
- `compare_metrics`

The Go app still appends usage entries to `logs/llm_logs.json` using the same project log schema:

- `llm_provider`
- `llm_latency_ms`
- `llm_input_tokens`
- `llm_output_tokens`
- `llm_success`
- `context` when `LOG_LEVEL=DEBUG`

The wrapper enables `save_state=True`, so local runs can appear in the `.railtracks` directory for visualization.

The comparison wrapper also writes the combined comparison result to:

- `logs/llm_comparisons.json`

Each comparison record includes the prompt, both providers' metrics, and the terminal summary text such as:

```text
Comparison:
CLOD latency: 4790 ms
OpenRouter latency: 2867 ms
Faster provider: openrouter
CLOD input tokens: 82
OpenRouter input tokens: 92
Lower input tokens: clod
CLOD output tokens: 112
OpenRouter output tokens: 675
Lower output tokens: clod
CLOD success: true
OpenRouter success: true
Higher success score: tie
```

If the `railtracks` command is not on your shell path, try:

```bash
python -m railtracks init
python -m railtracks viz
```

Reference docs used here:

- Railtracks homepage: `https://railtracks.org/`
- Railtracks GitHub quickstart examples: `https://github.com/RailtownAI/railtracks/`
- Railtracks visualization docs: `https://railtownai.github.io/railtracks/observability/visualization/`

## Planned Receipt Requirements

When receipt ingestion is added later, each receipt should include:

- `purchase_time`
- `store_name`
- `address`
- at least one visible item name with its cost
