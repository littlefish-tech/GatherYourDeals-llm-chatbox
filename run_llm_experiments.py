import argparse
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
LLM_LOG_PATH = PROJECT_ROOT / "logs" / "llm_logs.json"
COMPARISON_LOG_PATH = PROJECT_ROOT / "logs" / "llm_comparisons.json"
SUMMARY_LOG_PATH = PROJECT_ROOT / "logs" / "llm_summary.json"
SUMMARY_HISTORY_PATH = PROJECT_ROOT / "logs" / "llm_batch_summaries.json"
DEFAULT_PROMPTS_PATH = PROJECT_ROOT / "experiment_prompts.txt"


@dataclass
class ProviderRun:
    llm_provider: str
    llm_latency_ms: int
    llm_input_tokens: int
    llm_output_tokens: int
    llm_success: bool
    response: str
    provider_name: str
    llm_cost_usd: float | None = None


def read_json_array(path: Path) -> list[dict]:
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    data = json.loads(content)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected {path} to contain a JSON array.")
    return data


def write_json_array(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


def extract_response(stdout: str) -> str:
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

    lines = []
    for line in response_text[:stop_index].splitlines():
        if line.strip():
            lines.append(line)
    return "\n".join(lines).strip()


def run_go_for_provider(prompt: str, provider: str) -> ProviderRun:
    env = dict(os.environ)
    env["LLM_PROVIDER"] = provider
    display_name = "CLOD" if provider == "clod" else "OpenRouter"

    print(f"[{display_name}] Starting provider run...")

    before_count = len(read_json_array(LLM_LOG_PATH))
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

    log_entries = read_json_array(LLM_LOG_PATH)
    if len(log_entries) <= before_count:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        details = stderr or stdout or f"No new llm_logs.json entry was written for provider {provider}."
        print(f"[{display_name}] Failed before logging.")
        raise RuntimeError(f"{provider} run did not produce a log entry. Go CLI output: {details}")

    response = extract_response(completed.stdout)
    if not response:
        raise RuntimeError(f"No response was captured from the Go CLI output for provider {provider}.")

    log_entry = log_entries[-1]
    print(
        f"[{display_name}] Completed. "
        f"latency={log_entry['llm_latency_ms']} ms, "
        f"input_tokens={log_entry.get('llm_input_tokens', 0)}, "
        f"output_tokens={log_entry.get('llm_output_tokens', 0)}, "
        f"success={str(log_entry['llm_success']).lower()}"
    )
    return ProviderRun(
        llm_provider=log_entry.get("llm_provider", ""),
        llm_latency_ms=log_entry.get("llm_latency_ms", 0),
        llm_input_tokens=log_entry.get("llm_input_tokens", 0),
        llm_output_tokens=log_entry.get("llm_output_tokens", 0),
        llm_success=log_entry.get("llm_success", False),
        response=response,
        provider_name=provider,
        llm_cost_usd=log_entry.get("llm_cost_usd"),
    )


def build_comparison_summary(clod_result: ProviderRun, openrouter_result: ProviderRun) -> str:
    def pick_lower(left_name: str, left_value: int, right_name: str, right_value: int) -> str:
        if left_value == right_value:
            return "tie"
        return left_name if left_value < right_value else right_name

    def pick_success(left_name: str, left_value: bool, right_name: str, right_value: bool) -> str:
        if left_value == right_value:
            return "tie"
        return left_name if left_value else right_name

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


def log_comparison(prompt: str, clod_result: ProviderRun, openrouter_result: ProviderRun) -> dict:
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
        "summary": build_comparison_summary(clod_result, openrouter_result),
    }

    if clod_result.llm_cost_usd is not None:
        entry["clod"]["llm_cost_usd"] = clod_result.llm_cost_usd
    if openrouter_result.llm_cost_usd is not None:
        entry["openrouter"]["llm_cost_usd"] = openrouter_result.llm_cost_usd

    entries = read_json_array(COMPARISON_LOG_PATH)
    entries.append(entry)
    write_json_array(COMPARISON_LOG_PATH, entries)
    return entry


def load_prompts(path: Path) -> list[str]:
    prompts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        prompts.append(line)
    if not prompts:
        raise RuntimeError(f"No prompts found in {path}.")
    return prompts


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    rank = math.ceil((pct / 100.0) * len(sorted_values))
    index = min(max(rank - 1, 0), len(sorted_values) - 1)
    return sorted_values[index]


def metric_summary(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "min": None,
            "max": None,
            "p50": None,
        }

    avg = sum(values) / len(values)
    return {
        "count": len(values),
        "avg": round(avg, 4),
        "min": min(values),
        "max": max(values),
        "p50": percentile(values, 50),
    }


def build_batch_summary(batch_id: str, prompt_count: int, comparisons: list[dict]) -> dict:
    provider_records = {"clod": [], "openrouter": []}
    for comparison in comparisons:
        provider_records["clod"].append(comparison["clod"])
        provider_records["openrouter"].append(comparison["openrouter"])

    providers = {}
    for provider_name, records in provider_records.items():
        latencies = [record["llm_latency_ms"] for record in records]
        input_tokens = [record.get("llm_input_tokens", 0) for record in records]
        output_tokens = [record.get("llm_output_tokens", 0) for record in records]
        costs = [record["llm_cost_usd"] for record in records if "llm_cost_usd" in record]
        successes = [1 if record.get("llm_success") else 0 for record in records]

        providers[provider_name] = {
            "provider": provider_name,
            "model": records[0].get("llm_provider", "") if records else "",
            "sample_count": len(records),
            "success_rate": round(sum(successes) / len(successes), 4) if successes else None,
            "latency_ms": metric_summary(latencies),
            "input_tokens": metric_summary(input_tokens),
            "output_tokens": metric_summary(output_tokens),
            "cost_usd": metric_summary(costs),
        }

    return {
        "batch_id": batch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_count": prompt_count,
        "comparison_count": len(comparisons),
        "notes": [
            "This summary emphasizes avg, min, max, and p50 because they are more informative for small batches.",
            "Higher percentiles can be added later if the experiment size becomes much larger.",
        ],
        "providers": providers,
    }


def run_batch(prompts_path: Path) -> dict:
    prompts = load_prompts(prompts_path)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    comparisons = []

    print(f"Running {len(prompts)} prompts from {prompts_path}...")
    for index, prompt in enumerate(prompts, start=1):
        print()
        print(f"[Batch {batch_id}] Prompt {index}/{len(prompts)}: {prompt}")
        clod_result = run_go_for_provider(prompt, "clod")
        openrouter_result = run_go_for_provider(prompt, "openrouter")
        comparisons.append(log_comparison(prompt, clod_result, openrouter_result))

    summary = build_batch_summary(batch_id, len(prompts), comparisons)
    write_json_array(SUMMARY_HISTORY_PATH, read_json_array(SUMMARY_HISTORY_PATH) + [summary])
    SUMMARY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_LOG_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def summarize_existing() -> dict:
    comparisons = read_json_array(COMPARISON_LOG_PATH)
    if not comparisons:
        raise RuntimeError("No comparison entries found in logs/llm_comparisons.json.")
    summary = build_batch_summary("existing-log-summary", len(comparisons), comparisons)
    SUMMARY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_LOG_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run batch LLM test-case evaluation across providers and write summary stats.")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS_PATH, help="Path to a text file with one prompt per line.")
    parser.add_argument("--summarize-only", action="store_true", help="Skip new runs and summarize existing comparison logs.")
    args = parser.parse_args()

    if args.summarize_only:
        summary = summarize_existing()
        print(json.dumps(summary, indent=2))
        return

    if not args.prompts.exists():
        raise RuntimeError(f"Prompt file not found: {args.prompts}")

    summary = run_batch(args.prompts)
    print()
    print("Batch summary written to logs/llm_summary.json")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
