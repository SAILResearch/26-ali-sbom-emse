"""Share of returning contributors per format, with a chi-square test (RQ2).

A returning contributor made at least two commits to a repository. Each contributor is
counted once per repository and format, as in main.ipynb. Reads commit_counts_by_repo.pkl
and CycloneNSpdxTools.csv from this directory.

Usage: python RQ2-tools/returning_contributor_rate.py
"""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

HERE = Path(__file__).resolve().parent

df = pd.read_csv(HERE / "CycloneNSpdxTools.csv")
with open(HERE / "commit_counts_by_repo.pkl", "rb") as fh:
    commit_counts = pickle.load(fh)

counts = {}
for fmt in ["SPDX", "CycloneDx"]:
    per_contributor = [v for repo in df.loc[df.Format == fmt, "Repo"] for v in commit_counts[repo].values()]
    counts[fmt] = (sum(v >= 2 for v in per_contributor), len(per_contributor))

table = [[ret, total - ret] for ret, total in counts.values()]
chi2, p, _, _ = chi2_contingency(table, correction=False)
n = sum(sum(row) for row in table)
for fmt, (ret, total) in counts.items():
    print(f"{fmt}: {ret} of {total} contributors return ({100 * ret / total:.1f}%)")
print(f"chi2 = {chi2:.2f}, p = {p:.3g}, phi = {np.sqrt(chi2 / n):.3f}")
