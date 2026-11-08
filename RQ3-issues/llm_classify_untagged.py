#!/usr/bin/env python3
"""
LLM classification of ALL GitHub issues using our 14-category tag taxonomy.

Reads from issues_with_content.csv (produced by scrape_issue_content.py).
Targets ALL rows where fetch_status == ok (both tagged and untagged issues).
Uses a local vLLM endpoint by default, or OpenRouter as fallback.

Usage:
    python llm_classify_untagged.py
    VLLM_BASE_URL=http://localhost:8001/v1 python llm_classify_untagged.py
    DRY_RUN=1 python llm_classify_untagged.py   # prints first 3 prompts, exits

Prerequisite:
    python scrape_issue_content.py   # builds issues_with_content.csv first
"""

import os, time, json, re
import pandas as pd
import requests
import backoff
from pathlib import Path
from dotenv import load_dotenv

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env", override=True)

# Local vLLM endpoint; falls back to OpenRouter if not set
VLLM_BASE_URL      = os.environ.get("VLLM_BASE_URL", "http://elmyra.cs.queensu.ca/v1")
MODEL_ID           = os.environ.get("MODEL_ID", "devstral-small-2")
# OpenRouter key only needed when not using local vLLM
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MAX_RETRIES        = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY        = float(os.environ.get("RETRY_DELAY", "2.0"))
MIN_YEAR           = int(os.environ.get("MIN_YEAR", "2018"))
DRY_RUN            = os.environ.get("DRY_RUN", "0") == "1"
CONTENT_FILE       = BASE_DIR / "issues_with_content.csv"
OUT_FILE           = BASE_DIR / f"llm_classified_issues_{MODEL_ID.replace('/', '_')}.csv"

# ── 14-category taxonomy (derived from categories.csv + tag-to-category mapping) ──
CATEGORIES = [
    "Bug Fixes and Defects",
    "Code Quality",
    "Community Engagement and Support",
    "Configuration",
    "Continuous Integration and Deployment (CI/CD)",
    "Documentation",
    "Feature Development and Enhancement",
    "Integration and Interfacing",
    "Libraries",
    "Licensing",
    "Code Components",
    "Release Management and Versioning",
    "User Interface and Outputs",
    "Technical Debt",
]

CATEGORY_DESCRIPTIONS = {
    "Bug Fixes and Defects":
        "Issues reporting incorrect behavior, crashes, false positives/negatives, regressions, test failures, or stale/inactive issues awaiting resolution.",
    "Code Quality":
        "Refactoring, performance improvements, code style, linting, non-functional code improvements, and improvements to how the tool generates or processes package formats (e.g., improving output quality or generation logic — not implementing a new scanner or parser). Also includes internal maintenance items marked to be excluded from changelogs.",
    "Community Engagement and Support":
        "User questions, help-wanted requests, community discussions, mentorship (GSoC/LFX), upstream coordination. Use this for any issue that is primarily a question or support request from an end user.",
    "Configuration":
        "Installation, packaging, Docker, Helm, dependency management, environment setup.",
    "Continuous Integration and Deployment (CI/CD)":
        "CI pipeline issues, GitHub Actions, CD workflows, automated build and test infrastructure.",
    "Documentation":
        "Missing, incorrect, or improved documentation, API docs, examples, READMEs.",
    "Feature Development and Enhancement":
        "New features, enhancements, proposals, must-have / nice-to-have improvements. Also includes security-related enhancement requests (e.g., adding vulnerability scanning, SBOM security profiles, supply-chain risk features — not bug reports that happen to have security implications). This is the broadest category — use it for any improvement or enhancement request that does not belong to a more specific category (Licensing, CI/CD, Documentation, Configuration, etc.).",
    "Integration and Interfacing":
        "Support for specific language ecosystems (Java, JS, Go, Python, Ruby, Rust), OS support, webhooks, plugin integrations.",
    "Libraries":
        "Issues about the public API surface or library-level contracts of core SPDX/CDX libraries (e.g., method signatures, API stability, library-level bugs in spdx-utils). Use Code Components for issues about what those libraries parse, scan, or represent.",
    "Licensing":
        "License detection, copyright scanning, license review, new license submissions, SPDX license list updates.",
    "Code Components":
        "Implementing or fixing parsers, analyzers, scanners, serialization, data model, I/O, and package format support — as opposed to improving their output quality (which belongs in Code Quality).",
    "Release Management and Versioning":
        "Breaking changes, release planning, versioning, changelogs, pending releases. Does NOT include internal housekeeping items simply excluded from changelog entries.",
    "User Interface and Outputs":
        "GUI, CLI output, end-user-facing behavior, report formats. Issues about the CLI as an interface (not CLI as an ecosystem integration target) belong here.",
    "Technical Debt":
        "Technical debt cleanup, refactoring debt, long-term maintenance work. Does not need to be explicitly labeled — infer from issue content discussing cleanup of legacy code, accumulated shortcuts, or deferred maintenance.",
}

CATEGORY_LIST_STR = "\n".join(f"  {i+1:2d}. {c}" for i, c in enumerate(CATEGORIES))

SYSTEM_PROMPT = f"""You are an expert software engineering researcher classifying GitHub issues from SBOM (Software Bill of Materials) tool repositories.

You will be given a GitHub issue title and body. Classify it into ONE OR MORE of the following 14 categories (most issues belong to 1-2 categories):

{CATEGORY_LIST_STR}

Category descriptions:
{chr(10).join(f'  - {c}: {d}' for c, d in CATEGORY_DESCRIPTIONS.items())}

Rules:
- Always assign the best-fitting category even if the match is imperfect. Only return an empty list if the issue is completely off-topic (e.g., spam, test issue, unrelated to software development).
- Most issues warrant 1 category. A clearly multi-topic issue may warrant 2–3; do not force secondary categories if they are a stretch.
- Prefer specificity: if an issue matches both a general category (Bug Fixes) and a specific one (Technical Debt or Licensing), include both.
- Respond with ONLY a JSON object: {{"categories": ["<exact category name>", ...], "reasoning": "<one sentence>"}}
- Do not add any text outside the JSON object.

Examples:

Issue title: "Wrong SPDX license identifier emitted for Apache-2.0 with exceptions"
Issue body: "When generating an SPDX document, the license expression for Apache-2.0 WITH LLVM-exception is written as 'Apache-2.0-LLVM-exception' instead of the correct 'Apache-2.0 WITH LLVM-exception'. This causes validation failures downstream."
{{"categories": ["Bug Fixes and Defects", "Licensing"], "reasoning": "The issue reports incorrect output (bug) specifically in license expression formatting, so both the defect category and the licensing-specific category apply."}}

Issue title: "Add Rust/Cargo ecosystem support"
Issue body: "Currently the tool has no support for Rust projects using Cargo. We should be able to scan Cargo.toml and Cargo.lock files to enumerate crate dependencies and include them in the generated SBOM."
{{"categories": ["Integration and Interfacing"], "reasoning": "This is a request to add support for a new language ecosystem (Rust/Cargo), which is the definition of Integration and Interfacing."}}

Issue title: "Refactor PackageURL parsing to reduce duplication across parsers"
Issue body: "The PackageURL parsing logic is copy-pasted across 6 different ecosystem parsers. We should extract it into a shared utility to reduce maintenance burden and prevent drift. This has been on the backlog for over a year."
{{"categories": ["Code Quality", "Technical Debt"], "reasoning": "The issue describes deduplication refactoring (Code Quality) driven by long-deferred accumulated duplication (Technical Debt), so both apply."}}
"""

# ── Load all issues from content cache ──────────────────────────────────────

def load_all_issues() -> pd.DataFrame:
    """
    Read issues_with_content.csv (from scrape_issue_content.py).
    Filters to: fetch_status==ok, year>=MIN_YEAR.
    Includes both tagged and untagged issues.
    """
    if not CONTENT_FILE.exists():
        raise FileNotFoundError(
            f"{CONTENT_FILE} not found.\n"
            "Run scrape_issue_content.py first to build the content cache."
        )

    df = pd.read_csv(CONTENT_FILE)

    # Year filter
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = df[df["created_at"].dt.year >= MIN_YEAR].copy()

    # Only successfully fetched rows
    df = df[df["fetch_status"] == "ok"].copy()

    spdx_n = (df["format"] == "spdx").sum()
    cdx_n  = (df["format"] == "cdx").sum()
    print(f"  All issues (>=2018, fetch ok): spdx={spdx_n}  cdx={cdx_n}  total={len(df)}")
    return df


# ── OpenRouter API call ──────────────────────────────────────────────────────

class _RateLimited(Exception):
    pass

class _ModelLoading(Exception):
    pass


@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.Timeout, requests.exceptions.ConnectionError, _RateLimited),
    max_tries=8,
    base=2,
    factor=1.5,
    jitter=backoff.full_jitter,
    on_backoff=lambda d: print(f"    backoff {d['wait']:.1f}s"),
)
def _call_api(payload: dict, headers: dict) -> str:
    resp = requests.post(
        f"{VLLM_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=300,
    )
    if resp.status_code == 503:
        raise _ModelLoading("HTTP 503 — model still loading")
    if resp.status_code == 429:
        raise _RateLimited(f"HTTP 429")
    resp.raise_for_status()
    data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    content = msg.get("content") or ""
    # Strip <think>...</think> blocks emitted by reasoning models before the JSON
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    if not content:
        # Fallback: some models put the answer only in the reasoning field
        reasoning = msg.get("reasoning", "") or ""
        for detail in msg.get("reasoning_details", []):
            reasoning += detail.get("text", "")
        content = re.sub(r"<think>.*?</think>", "", reasoning, flags=re.DOTALL).strip()
    if not content:
        raise ValueError(f"empty content, finish_reason={((data.get('choices') or [{}])[0].get('finish_reason'))}")
    return content


def wake_model(poll_interval: int = 30, max_wait: int = 1800):
    """
    Send a cheap ping to wake an on-demand model, then poll until it responds 200.
    max_wait=1800s covers the worst-case ~13-min cold start with margin.
    """
    ping_payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Content-Type": "application/json"}

    print(f"  Waking model '{MODEL_ID}' (on-demand, cold-start up to ~13 min)...")
    # First request triggers the wake — 503 is expected
    try:
        requests.post(f"{VLLM_BASE_URL}/chat/completions", headers=headers,
                      json=ping_payload, timeout=10)
    except Exception:
        pass

    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval
        try:
            r = requests.post(f"{VLLM_BASE_URL}/chat/completions", headers=headers,
                              json=ping_payload, timeout=30)
            if r.status_code == 200:
                print(f"  Model ready after ~{elapsed}s.")
                return
            print(f"  still loading ({r.status_code})... {elapsed}s elapsed")
        except Exception as e:
            print(f"  poll error: {e} — retrying")

    raise RuntimeError(f"Model '{MODEL_ID}' did not become ready within {max_wait}s.")


def _call_api_with_wake(payload: dict, headers: dict) -> str:
    """Call _call_api; if 503, wake the model and retry once."""
    try:
        return _call_api(payload, headers)
    except _ModelLoading:
        print("  503 received mid-run — model went to sleep, re-waking...")
        wake_model()
        return _call_api(payload, headers)


def _valid_categories(cats) -> list[str]:
    """Return only category names that are in the taxonomy."""
    if isinstance(cats, str):
        cats = [cats]
    return [c for c in (cats or []) if c in CATEGORIES]


def classify_issue(title: str, body: str, url: str) -> dict:
    """Returns dict with 'categories' (list), 'confidence', 'reasoning'."""
    body_trunc = body[:1600] + ("\n...\n" + body[-400:] if len(body) > 2100 else "")
    user_msg = f"GitHub issue URL: {url}\n\nTitle: {title}\n\nBody:\n{body_trunc}"

    headers = {"Content-Type": "application/json"}
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
    }

    for attempt in range(MAX_RETRIES):
        try:
            content = _call_api_with_wake(payload, headers)
            if '{' in content:
                decoder = json.JSONDecoder()
                braces = list(re.finditer(r'\{', content))

                def _scan(positions):
                    for m in positions:
                        try:
                            obj, _ = decoder.raw_decode(content, m.start())
                            cats = obj.get("categories") or ([obj["category"]] if obj.get("category") else [])
                            if _valid_categories(cats):
                                return obj
                        except json.JSONDecodeError:
                            continue
                    return None

                # Forward pass (normal models put JSON first)
                found_result = _scan(braces)
                # Backward pass (reasoning models put JSON last)
                if found_result is None:
                    found_result = _scan(reversed(braces))

                if found_result is not None:
                    valid = _valid_categories(
                        found_result.get("categories") or
                        ([found_result["category"]] if found_result.get("category") else [])
                    )
                    return {
                        "categories": valid,
                        "confidence": "high",
                        "reasoning":  found_result.get("reasoning", ""),
                    }

                # Check if any JSON object has explicit empty categories (off-topic/spam)
                for m in braces:
                    try:
                        obj, _ = decoder.raw_decode(content, m.start())
                        if isinstance(obj.get("categories"), list) and obj["categories"] == []:
                            print(f"    SKIP: off-topic/spam: {obj.get('reasoning','')[:120]}")
                            return {"categories": [], "confidence": "high", "reasoning": obj.get("reasoning", "")}
                    except json.JSONDecodeError:
                        continue

                print(f"    WARNING: no category found in response ({len(content)} chars): {content[-300:]!r}")
        except Exception as e:
            short = str(e)[:120]
            print(f"    err attempt {attempt+1}: {short}")
        time.sleep(RETRY_DELAY * (attempt + 1))

    print(f"    WARNING: all {MAX_RETRIES} retries exhausted for {url} — assigning empty categories")
    return {"categories": [], "confidence": "low", "reasoning": "classification failed after all retries"}


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Model:    {MODEL_ID}")
    print(f"Endpoint: {VLLM_BASE_URL}")
    print(f"Output:   {OUT_FILE}")
    print(f"Source:   {CONTENT_FILE}")
    print(f"Min year: {MIN_YEAR}\n")

    all_issues = load_all_issues()
    wake_model()

    if DRY_RUN:
        print("\n── DRY RUN: first 3 issues ──")
        for _, row in all_issues.head(3).iterrows():
            print(f"\nURL:    {row['issue_url']}")
            print(f"Format: {row['format']}")
            print(f"Title:  {row['title']}")
            print(f"Body:   {str(row['body'])[:200]}\n---")
        return

    # Resume support: skip issues already present in the output file
    if OUT_FILE.exists():
        done = pd.read_csv(OUT_FILE)
        done_urls = set(done["issue_url"].dropna().unique().tolist())
        print(f"Resuming: {len(done_urls)} issues already classified ({len(done)} rows)")
    else:
        done = pd.DataFrame()
        done_urls = set()

    results = []
    remaining = [r for _, r in all_issues.iterrows() if str(r["issue_url"]) not in done_urls]
    total_new = len(remaining)
    print(f"  Issues left to label: {total_new}")

    for new_i, row in enumerate(remaining, 1):
        url    = str(row["issue_url"])
        fmt    = str(row["format"])
        repo   = str(row.get("repo", ""))
        title  = str(row.get("title", ""))
        body   = str(row.get("body", ""))
        print(f"  [{new_i}/{total_new}] {fmt.upper()} | {title[:65]}")
        result = classify_issue(title, body, url)
        cats = result["categories"]
        if not cats:
            print(f"           → SKIPPED (off-topic/spam, no categories)")
            done_urls.add(url)  # don't revisit on resume
            continue
        print(f"           → {', '.join(cats)}")

        new_row = {
            "issue_url":      url,
            "format":         fmt,
            "repo":           repo,
            "created_at":     row.get("created_at", ""),
            "title":          title,
            "devstral_categories": str(cats),
            "model":          MODEL_ID,
        }
        results.append(new_row)
        _save(done, results)

        time.sleep(0.3)

    final = pd.concat([done, pd.DataFrame(results)], ignore_index=True) if results else done
    print(f"\nDone. {len(final)} issues classified → {OUT_FILE}")


def _save(done: pd.DataFrame, new_rows: list[dict]):
    rows = pd.DataFrame(new_rows)
    out  = pd.concat([done, rows], ignore_index=True) if not done.empty else rows
    out.to_csv(OUT_FILE, index=False)


if __name__ == "__main__":
    main()
