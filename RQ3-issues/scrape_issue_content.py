#!/usr/bin/env python3
"""
Scrape GitHub issue title + body for all issues in SpdxIssues.csv and CdxIssues.csv.

Writes: issues_with_content.csv
Columns: issue_url, format (spdx|cdx), repo, state, created_at, closed_at,
         tags, year, title, body, fetch_status

This is a one-time scrape step. The classifier (llm_classify_untagged.py) reads
from this file instead of hitting GitHub each run.

Usage:
    python scrape_issue_content.py               # scrape everything
    LIMIT=100 python scrape_issue_content.py     # first N per format (testing)
    RESUME=1  python scrape_issue_content.py     # skip already-fetched URLs
"""

import os, time, itertools
import pandas as pd
import requests
import backoff
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env", override=True)

OUT_FILE     = BASE_DIR / "issues_with_content.csv"
MAX_RETRIES  = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY  = float(os.environ.get("RETRY_DELAY", "1.5"))
LIMIT        = int(os.environ.get("LIMIT", "0"))   # 0 = no limit
RESUME       = os.environ.get("RESUME", "0") == "1"
CHECKPOINT_N = 200   # save every N rows


# ── GitHub token rotation ────────────────────────────────────────────────────

def _load_tokens() -> list[str]:
    tokens = []
    for i in range(1, 30):
        t = os.environ.get(f"GITHUB_TOKEN_{i}", "")
        if t:
            tokens.append(t)
    single = os.environ.get("GITHUB_TOKEN", "")
    if single and single not in tokens:
        tokens.append(single)
    return tokens

_TOKENS = _load_tokens()
_token_cycle = itertools.cycle(_TOKENS) if _TOKENS else None

def next_token() -> str:
    return next(_token_cycle) if _token_cycle else ""


# ── Fetch a single issue from GitHub API ────────────────────────────────────

class _RateLimited(Exception):
    pass

class _NotFound(Exception):
    pass

@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.Timeout, requests.exceptions.ConnectionError, _RateLimited),
    max_tries=8,
    base=2,
    factor=1.5,
    jitter=backoff.full_jitter,
    on_backoff=lambda details: print(
        f"    backoff: wait {details['wait']:.1f}s (attempt {details['tries']})"
    ),
)
def _get_issue(api_url: str, headers: dict) -> requests.Response:
    resp = requests.get(api_url, headers=headers, timeout=20)
    if resp.status_code == 404:
        raise _NotFound(api_url)
    if resp.status_code in (403, 429):
        headers["Authorization"] = f"token {next_token()}"
        raise _RateLimited(f"HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp


def fetch_issue(api_url: str) -> tuple[str, str, str]:
    """Return (title, body, status) where status is 'ok'|'not_found'|'error'."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    tok = next_token()
    if tok:
        headers["Authorization"] = f"token {tok}"
    try:
        resp  = _get_issue(api_url, headers)
        data  = resp.json()
        title = data.get("title") or ""
        body  = data.get("body")  or ""
        return title, body, "ok"
    except _NotFound:
        return "", "", "not_found"
    except Exception as e:
        print(f"    fetch failed: {e}")
        return "", "", "error"


# ── Load source CSVs ─────────────────────────────────────────────────────────

def load_csv(path: Path, fmt: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={
        "Issue URL": "issue_url",
        "State":     "state",
        "created_at": "created_at",
        "closed_at":  "closed_at",
        "Tags":       "tags",
        "Repo":       "repo",
        "Year":       "year",
    })
    df["format"] = fmt   # "spdx" or "cdx"
    keep = ["issue_url", "format", "repo", "state", "created_at", "closed_at", "tags", "year"]
    keep = [c for c in keep if c in df.columns]
    return df[keep].copy()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading source CSVs...")
    spdx = load_csv(BASE_DIR / "SpdxIssues.csv", "spdx")
    cdx  = load_csv(BASE_DIR / "CdxIssues.csv",  "cdx")
    all_issues = pd.concat([spdx, cdx], ignore_index=True)
    print(f"  spdx: {len(spdx)} rows")
    print(f"  cdx:  {len(cdx)} rows")
    print(f"  total: {len(all_issues)} rows")

    if LIMIT > 0:
        spdx_sample = spdx.head(LIMIT)
        cdx_sample  = cdx.head(LIMIT)
        all_issues  = pd.concat([spdx_sample, cdx_sample], ignore_index=True)
        print(f"  LIMIT={LIMIT} applied → {len(all_issues)} rows")

    # Resume: skip already-fetched URLs
    done_urls: set[str] = set()
    existing_rows: list[dict] = []
    if RESUME and OUT_FILE.exists():
        existing = pd.read_csv(OUT_FILE)
        done_urls = set(existing["issue_url"].dropna().tolist())
        existing_rows = existing.to_dict("records")
        print(f"Resuming: {len(done_urls)} already fetched, {len(all_issues) - len(done_urls)} remaining")

    print(f"\nTokens available: {len(_TOKENS)}")
    print(f"Output: {OUT_FILE}\n")

    new_rows: list[dict] = []
    total = len(all_issues)

    for i, row in enumerate(all_issues.itertuples(index=False), 1):
        url = str(row.issue_url)
        if url in done_urls:
            continue

        title, body, status = fetch_issue(url)

        new_rows.append({
            "issue_url":    url,
            "format":       row.format,
            "repo":         getattr(row, "repo", ""),
            "state":        getattr(row, "state", ""),
            "created_at":   getattr(row, "created_at", ""),
            "closed_at":    getattr(row, "closed_at", ""),
            "tags":         getattr(row, "tags", "[]"),
            "year":         getattr(row, "year", ""),
            "title":        title,
            "body":         body,
            "fetch_status": status,
        })

        label = f"[{i}/{total}] {row.format.upper()} {status}"
        print(f"  {label} | {title[:70]}" if title else f"  {label} | {url[-60:]}")

        # Checkpoint
        if len(new_rows) % CHECKPOINT_N == 0:
            _save(existing_rows + new_rows)
            print(f"  [checkpoint] {len(existing_rows) + len(new_rows)} rows saved")

        # Polite delay between requests
        time.sleep(0.5)

    _save(existing_rows + new_rows)
    total_saved = len(existing_rows) + len(new_rows)
    print(f"\nDone. {total_saved} rows → {OUT_FILE}")

    df = pd.DataFrame(existing_rows + new_rows)
    ok    = (df["fetch_status"] == "ok").sum()
    nf    = (df["fetch_status"] == "not_found").sum()
    err   = (df["fetch_status"] == "error").sum()
    print(f"  ok={ok}  not_found={nf}  error={err}")


def _save(rows: list[dict]):
    pd.DataFrame(rows).to_csv(OUT_FILE, index=False)


if __name__ == "__main__":
    main()
