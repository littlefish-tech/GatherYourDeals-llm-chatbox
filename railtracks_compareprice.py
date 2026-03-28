import asyncio
import json
import os
import subprocess
from pathlib import Path

import railtracks as rt
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent
LLM_LOG_PATH = PROJECT_ROOT / "logs" / "llm_logs.json"
COMPARISON_LOG_PATH = PROJECT_ROOT / "logs" / "llm_comparisons.json"


class ProviderRun(BaseModel):
    # One normalized result object for a single provider run.
    llm_provider: str
    llm_latency_ms: int
    llm_input_tokens: int
    llm_output_tokens: int
    llm_success: bool
    response: str
    provider_name: str


class ComparisonResult(BaseModel):
    # Combined payload used for both terminal output and comparison logging.
    summary: str
    clod_response: str
    openrouter_response: str
    clod_metrics: ProviderRun
    openrouter_metrics: ProviderRun


def extract_response(stdout: str) -> str:
    # Pull only the model answer back out of the interactive Go CLI output.
    marker = "Response:"
    if marker not in stdout:
        return stdout.strip()

    response_text = stdout.split(marker, 1)[1]
    stop_markers = [
        "Enter prompt (or type 'exit'):",
        "Do you have a receipt to scan? (yes/no or type 'exit'):",
        "Goodbye.",
    ]
    stop_index = len(response_text)
    for stop_marker in stop_markers:
        marker_index = response_text.find(stop_marker)
        if marker_index != -1 and marker_index < stop_index:
            stop_index = marker_index
    response_text = response_text[:stop_index]

    response_lines = []
    for line in response_text.splitlines():
        stripped = line.strip()
        if stripped == "":
            continue
        response_lines.append(line)

    return "\n".join(response_lines).strip()


def read_log_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        content = file.read().strip()

    if not content:
        return []

    entries = json.loads(content)
    if not isinstance(entries, list):
        raise RuntimeError(f"Expected {path} to contain a JSON array.")
    return entries


def write_log_entries(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)
        file.write("\n")


def run_go_for_provider(prompt: str, provider: str) -> ProviderRun:
    env = dict(os.environ)
    env["LLM_PROVIDER"] = provider
    display_name = "CLOD" if provider == "clod" else "OpenRouter"

    print(f"[{display_name}] Starting provider run...")

    before_count = len(read_log_entries(LLM_LOG_PATH))
    # Feed one prompt plus "exit" so the existing Go CLI can run unchanged.
    completed = subprocess.run(
        ["go", "run", "."],
        input=f"no\n{prompt}\nexit\n",
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        details = stderr or stdout or f"go run exited with code {completed.returncode}"
        print(f"[{display_name}] Failed.")
        raise RuntimeError(details)

    log_entries = read_log_entries(LLM_LOG_PATH)
    after_count = len(log_entries)
    if after_count <= before_count:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        details = stderr or stdout or f"No new llm_logs.json entry was written for provider {provider}."
        print(f"[{display_name}] Failed before logging.")
        raise RuntimeError(f"{provider} run did not produce a log entry. Go CLI output: {details}")

    response = extract_response(completed.stdout)
    if not response:
        raise RuntimeError(f"No response was captured from the Go CLI output for provider {provider}.")

    # Read the newest log row so Railtracks can compare provider metrics.
    log_entry = log_entries[-1]
    print(
        f"[{display_name}] Completed. "
        f"latency={log_entry['llm_latency_ms']} ms, "
        f"input_tokens={log_entry.get('llm_input_tokens', 0)}, "
        f"output_tokens={log_entry.get('llm_output_tokens', 0)}, "
        f"success={str(log_entry['llm_success']).lower()}"
    )
    return ProviderRun(
        llm_provider=log_entry["llm_provider"],
        llm_latency_ms=log_entry["llm_latency_ms"],
        llm_input_tokens=log_entry.get("llm_input_tokens", 0),
        llm_output_tokens=log_entry.get("llm_output_tokens", 0),
        llm_success=log_entry["llm_success"],
        response=response,
        provider_name=provider,
    )


def build_comparison_summary(clod_result: ProviderRun, openrouter_result: ProviderRun) -> str:
    lines = [
        "Comparison:",
        f"CLOD latency: {clod_result.llm_latency_ms} ms",
        f"OpenRouter latency: {openrouter_result.llm_latency_ms} ms",
        f"Faster provider: {pick_lower('clod', clod_result.llm_latency_ms, 'openrouter', openrouter_result.llm_latency_ms)}",
        f"CLOD input tokens: {clod_result.llm_input_tokens}",
        f"OpenRouter input tokens: {openrouter_result.llm_input_tokens}",
        f"Lower input tokens: {pick_lower('clod', clod_result.llm_input_tokens, 'openrouter', openrouter_result.llm_input_tokens)}",
        f"CLOD output tokens: {clod_result.llm_output_tokens}",
        f"OpenRouter output tokens: {openrouter_result.llm_output_tokens}",
        f"Lower output tokens: {pick_lower('clod', clod_result.llm_output_tokens, 'openrouter', openrouter_result.llm_output_tokens)}",
        f"CLOD success: {str(clod_result.llm_success).lower()}",
        f"OpenRouter success: {str(openrouter_result.llm_success).lower()}",
        f"Higher success score: {pick_success('clod', clod_result.llm_success, 'openrouter', openrouter_result.llm_success)}",
    ]
    return "\n".join(lines)


def build_terminal_output(comparison: ComparisonResult) -> str:
    # Show both provider answers first, then the numeric comparison summary.
    sections = [
        "CLOD Response:",
        comparison.clod_response,
        "",
        "OpenRouter Response:",
        comparison.openrouter_response,
        "",
        comparison.summary,
    ]
    return "\n".join(sections)


def pick_lower(left_name: str, left_value: int, right_name: str, right_value: int) -> str:
    if left_value == right_value:
        return "tie"
    if left_value < right_value:
        return left_name
    return right_name


def pick_success(left_name: str, left_value: bool, right_name: str, right_value: bool) -> str:
    if left_value == right_value:
        return "tie"
    if left_value:
        return left_name
    return right_name


def log_comparison(prompt: str, clod_result: ProviderRun, openrouter_result: ProviderRun, summary: str) -> None:
    # Persist a lightweight comparison record so repeated runs can be reviewed later.
    entry = {
        "prompt": prompt,
        "clod": {
            "llm_provider": clod_result.llm_provider,
            "llm_latency_ms": clod_result.llm_latency_ms,
            "llm_input_tokens": clod_result.llm_input_tokens,
            "llm_output_tokens": clod_result.llm_output_tokens,
            "llm_success": clod_result.llm_success,
        },
        "openrouter": {
            "llm_provider": openrouter_result.llm_provider,
            "llm_latency_ms": openrouter_result.llm_latency_ms,
            "llm_input_tokens": openrouter_result.llm_input_tokens,
            "llm_output_tokens": openrouter_result.llm_output_tokens,
            "llm_success": openrouter_result.llm_success,
        },
        "summary": summary,
    }

    entries = read_log_entries(COMPARISON_LOG_PATH)
    entries.append(entry)
    write_log_entries(COMPARISON_LOG_PATH, entries)


@rt.function_node
async def validate_prompt(prompt: str) -> str:
    # Keep input validation as its own node so failures are visible in Railtracks.
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompt cannot be empty.")
    return cleaned


@rt.function_node
async def run_clod(prompt: str) -> ProviderRun:
    return run_go_for_provider(prompt, "clod")


@rt.function_node
async def run_openrouter(prompt: str) -> ProviderRun:
    return run_go_for_provider(prompt, "openrouter")


@rt.function_node
async def compare_metrics(clod_result: ProviderRun, openrouter_result: ProviderRun) -> ComparisonResult:
    # Build the user-facing comparison after both provider calls have finished.
    summary = build_comparison_summary(clod_result, openrouter_result)
    return ComparisonResult(
        summary=summary,
        clod_response=clod_result.response,
        openrouter_response=openrouter_result.response,
        clod_metrics=clod_result,
        openrouter_metrics=openrouter_result,
    )


@rt.function_node
async def persist_comparison(prompt: str, comparison: ComparisonResult) -> str:
    # Log the metrics summary, then return the fuller terminal view with both responses.
    log_comparison(prompt, comparison.clod_metrics, comparison.openrouter_metrics, comparison.summary)
    return build_terminal_output(comparison)


@rt.function_node
async def compareprice_flow(prompt: str) -> str:
    # Track validation, each provider run, and persistence as separate nodes.
    normalized_prompt = await rt.call(validate_prompt, prompt)
    clod_result = await rt.call(run_clod, normalized_prompt)
    openrouter_result = await rt.call(run_openrouter, normalized_prompt)
    comparison = await rt.call(compare_metrics, clod_result, openrouter_result)
    return await rt.call(persist_comparison, normalized_prompt, comparison)


def main() -> None:
    rt.set_config(save_state=True)
    flow = rt.Flow(
        name="comparePrice Provider Comparison",
        entry_point=compareprice_flow,
    )

    print("comparePrice Railtracks comparison wrapper")
    print("This runs CLOD and OpenRouter as separate tracked nodes, then compares their metrics.")
    print("The current scan step is a placeholder. If you choose yes, the app will tell you scanning is not supported yet.")
    print("Type a grocery-related prompt, or type 'exit' to quit.")

    while True:
        scan_choice = input("Do you have a receipt to scan? (yes/no or type 'exit'): ").strip().lower()
        if not scan_choice:
            print("Please enter yes, no, or exit.")
            continue

        if scan_choice == "exit":
            print("Goodbye.")
            return

        if scan_choice in {"yes", "y"}:
            print("Receipt scanning is not supported yet in this app. Please add the receipt JSON to the output folder for now.")
        elif scan_choice not in {"no", "n"}:
            print("Please enter yes, no, or exit.")
            continue

        prompt = input("Enter prompt: ").strip()
        if not prompt:
            print("Prompt cannot be empty.")
            continue

        if prompt.lower() == "exit":
            print("Goodbye.")
            return

        try:
            result = asyncio.run(flow.ainvoke(prompt))
        except Exception as err:
            print()
            print(f"Comparison run failed: {err}")
            print("This session will usually appear as a partial trace in Railtracks.")
            print()
            continue
        print()
        print(getattr(result, "text", str(result)))
        print()


if __name__ == "__main__":
    main()
