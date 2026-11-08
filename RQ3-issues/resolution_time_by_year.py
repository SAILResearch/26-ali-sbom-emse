"""Resolution time of closed issue reports by creation year, CycloneDX versus SPDX (RQ3).

For each year from 2018 to 2023, compares the resolution times of closed issue reports with a
two-sided Mann-Whitney U test, Bonferroni-corrected over the six years, and reports Cliff's delta
(negative when CycloneDX resolution times are shorter). Issue reports created in 2024 are excluded
because the data end on 2024-02-10.

Usage: python RQ3-issues/resolution_time_by_year.py
"""

from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent
YEARS = range(2018, 2024)


def closed_by_year(path):
    df = pd.read_csv(path, low_memory=False)
    df["year"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce").dt.year
    df = df[(df.State == "closed") & df.year.isin(YEARS)]
    return {y: g.time_diff.dropna() / 86400 for y, g in df.groupby("year")}


def by_year():
    cdx = closed_by_year(HERE / "CdxIssues_dedup.csv")
    spdx = closed_by_year(HERE / "SpdxIssues_dedup.csv")
    rows = []
    for y in YEARS:
        c, s = cdx[y], spdx[y]
        res = mannwhitneyu(c, s, alternative="two-sided")
        rows.append(dict(year=y, n_cdx=len(c), n_spdx=len(s), mean_cdx=c.mean(), mean_spdx=s.mean(),
                         median_cdx=c.median(), median_spdx=s.median(), p=res.pvalue,
                         p_adj=min(1.0, res.pvalue * len(YEARS)),
                         delta=2 * res.statistic / (len(c) * len(s)) - 1))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(by_year().round(3).to_string(index=False))
