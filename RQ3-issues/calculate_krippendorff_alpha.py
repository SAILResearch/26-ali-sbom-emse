"""
Compute Krippendorff's Alpha from sample_issues.csv.

sample_issues.csv contains one row per issue with LLM and human tag lists:
  issue_url, format, repo, created_at, title, devstral_categories, human_categories, round

Alpha is computed as: 2 raters × (N_SAMPLE × 14) binary units, nominal level.

Usage:
    python RQ3-issues/reconcile_and_kappa.py
"""

import ast
import numpy as np
import pandas as pd
from pathlib import Path
import krippendorff

SAMPLE_FILE = Path("RQ3-issues/sample_issues.csv")

CATEGORIES = [
    "Bug Fixes and Defects",
    "Code Components",
    "Code Quality",
    "Community Engagement and Support",
    "Configuration",
    "Continuous Integration and Deployment (CI/CD)",
    "Documentation",
    "Feature Development and Enhancement",
    "Integration and Interfacing",
    "Libraries",
    "Licensing",
    "Release Management and Versioning",
    "Technical Debt",
    "User Interface and Outputs",
]


def to_binary_row(cat_str: str) -> np.ndarray:
    try:
        cats = set(ast.literal_eval(cat_str))
    except (ValueError, SyntaxError):
        cats = set()
    return np.array([1 if c in cats else 0 for c in CATEGORIES], dtype=float)


def main():
    print(f"Loading {SAMPLE_FILE}...")
    df = pd.read_csv(SAMPLE_FILE)
    print(f"  {len(df)} issues")

    q_matrix = np.stack(df["devstral_categories"].apply(to_binary_row).values)
    m_matrix = np.stack(df["human_categories"].apply(to_binary_row).values)

    reliability_matrix = np.array([
        q_matrix.flatten(),
        m_matrix.flatten(),
    ])

    alpha = round(krippendorff.alpha(
        reliability_data=reliability_matrix,
        level_of_measurement="nominal",
    ), 4)

    print(f"  Krippendorff's Alpha (overall, n={len(df)} issues): {alpha:.4f}")

    # Agreement by annotation round: round 1 = issues already annotated before the prompt was
    # revised (git commit cc6a2c0), round 2 = issues added to the sample afterwards
    if "round" in df.columns:
        for rnd, sub in df.groupby("round"):
            idx = sub.index.to_numpy()
            a_r = krippendorff.alpha(
                reliability_data=np.array([q_matrix[idx].flatten(), m_matrix[idx].flatten()]),
                level_of_measurement="nominal",
            )
            print(f"  Round {rnd}: n={len(sub)}, alpha={a_r:.4f}")

    # Per-category agreement of the LLM labels against the human labels
    print(f"\n  {'category':48s} {'alpha':>6s} {'prec':>6s} {'rec':>6s} {'F1':>6s} {'human n':>8s}")
    for j, cat in enumerate(CATEGORIES):
        q, m = q_matrix[:, j], m_matrix[:, j]
        tp = float(((q == 1) & (m == 1)).sum())
        prec = tp / q.sum() if q.sum() else float("nan")
        rec = tp / m.sum() if m.sum() else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else float("nan")
        a = krippendorff.alpha(reliability_data=np.array([q, m]), level_of_measurement="nominal")
        print(f"  {cat:48s} {a:6.3f} {prec:6.3f} {rec:6.3f} {f1:6.3f} {int(m.sum()):8d}")


if __name__ == "__main__":
    main()
