"""
build_issue_categories.py

Builds the deduplicated issue datasets and the per-issue category assignments used by
issues.R and tags.R.

Why deduplication: the tool lists contain repositories that appear more than once (a tool-center
entry and a contributing fork of the same repository), so the raw issue files list the same
issue several times within a format. Every issue is therefore kept once per (format, issue URL).
An issue that belongs to repositories of both formats still counts once in each format.

Category assignment (as described in the paper): the LLM categories (devstral-small-2, first
output per issue) are used for every issue; the human labels of the 379-issue validation sample
override them. Issues that the LLM could not label (issue text not fetchable) fall back to the
categories mapped from the maintainers' tags (categories.csv); issues with neither stay unlabeled.

Outputs (RQ3-issues/):
  CdxIssues_dedup.csv, SpdxIssues_dedup.csv  one row per issue (post-2018 filter is applied in R)
  issue_categories.csv                       one row per (format, issue, category) with label source
  tag_categories_dedup.csv                   tag-derived categories only (cross-check view)
"""
import ast
from pathlib import Path
import pandas as pd

BASE = Path(__file__).parent
CATEGORIES = [
    "Bug Fixes and Defects", "Code Components", "Code Quality",
    "Community Engagement and Support", "Configuration",
    "Continuous Integration and Deployment (CI/CD)", "Documentation",
    "Feature Development and Enhancement", "Integration and Interfacing", "Libraries",
    "Licensing", "Release Management and Versioning", "Technical Debt",
    "User Interface and Outputs",
]


def parse_cats(val):
    try:
        out = ast.literal_eval(str(val))
        return [c for c in out if c in CATEGORIES] if isinstance(out, list) else []
    except Exception:
        return []


def parse_tags(val):
    s = str(val).strip()
    if len(s) <= 2:
        return []
    return [t.strip() for t in s.strip("[]").replace("'", "").split(", ") if t.strip()]


raw = {"cdx": pd.read_csv(BASE / "CdxIssues.csv"), "spdx": pd.read_csv(BASE / "SpdxIssues.csv")}
llm = pd.read_csv(BASE / "llm_classified_issues_devstral-small-2.csv")
llm = llm.drop_duplicates("issue_url", keep="first").set_index("issue_url")["devstral_categories"].map(parse_cats)
sample = pd.read_csv(BASE / "sample_issues.csv")
human = {r.issue_url: parse_cats(r.human_categories) for r in sample.itertuples()}
human = {k: v for k, v in human.items() if v}
cat_map = pd.read_csv(BASE / "categories.csv")
cat_map["Tags"] = cat_map["Tags"].astype(str)
tag2cat = {}
for r in cat_map.itertuples():
    tag2cat.setdefault((r.identifier, r.Tags), set()).add(r.category)
ident = {"cdx": "CycloneDX", "spdx": "SPDX"}

issue_rows, cat_rows, tag_rows = [], [], []
for fmt, df in raw.items():
    before = len(df)
    df = df.drop_duplicates("Issue URL", keep="first").copy()
    df["Year"] = df["Year"].astype(int)
    df.to_csv(BASE / f"{'Cdx' if fmt == 'cdx' else 'Spdx'}Issues_dedup.csv", index=False)
    print(fmt, "rows", before, "-> distinct issues", len(df))
    for r in df.itertuples():
        if r.Year < 2018:
            continue
        resolve = r.time_diff if r.State == "closed" else 0
        tags = parse_tags(r.Tags)
        tag_cats = sorted({c for t in tags for c in tag2cat.get((ident[fmt], t), [])})
        url = r._1
        if url in human:
            cats, src = human[url], "human"
        elif url in llm.index:
            cats, src = llm[url], "llm"
        elif tag_cats:
            cats, src = tag_cats, "tag-fallback"
        else:
            cats, src = [], "unlabeled"
        base = dict(identifier=ident[fmt], Issue_URL=url, Repo=r.Repo, State=r.State,
                    Year=r.Year, resolve_time_sec=resolve, n_tags=len(tags), source=src)
        if not cats:
            cat_rows.append(dict(base, category=""))
        for c in cats:
            cat_rows.append(dict(base, category=c))
        for c in tag_cats:
            tag_rows.append(dict(base, category=c))
out = pd.DataFrame(cat_rows)
out.to_csv(BASE / "issue_categories.csv", index=False)
pd.DataFrame(tag_rows).to_csv(BASE / "tag_categories_dedup.csv", index=False)
iss = out.drop_duplicates(["identifier", "Issue_URL"])
print(iss.groupby("identifier").size())
print(iss.groupby(["identifier", "source"]).size())
