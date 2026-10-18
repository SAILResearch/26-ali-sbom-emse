# The State of the SBOM Tool Ecosystems: A Comparative Analysis of SPDX and CycloneDX

Replication package for an empirical study of the SPDX and CycloneDX tool ecosystems.

## Contents

- [Research Questions](#research-questions)
- [Repository Structure](#repository-structure)
- [Environment](#environment)
- [Citation](#citation)

## Research Questions

| Module | Research question | Scope |
|---|---|---|
| [RQ1-usecases](RQ1-usecases/) | Which use cases do SBOM tools support? | 108 open-source and 62 proprietary tools |
| [RQ2-tools](RQ2-tools/) | How healthy are the open-source SBOM tools? | 601 GitHub repositories (145 CycloneDX, 456 SPDX) |
| [RQ3-issues](RQ3-issues/) | What issues do these tools report, and how fast are they resolved? | 26,853 issues since 2018 (14,811 CycloneDX, 12,042 SPDX) |
| [RQ4-project](RQ4-project/) | How healthy are the projects that use these tools? | Top 250 projects per format |

Data collection date: May 1, 2025.

## Repository Structure

```text
.
├── RQ1-usecases/
├── RQ2-tools/
├── RQ3-issues/
├── RQ4-project/
├── methodology-figure/
├── wip-24-ali-sbom-emse/    # LaTeX manuscript (separate git project)
├── comments/                # Review rounds and response letters
├── docs/                    # Project web page
└── requirements.txt
```

### RQ1-usecases

| File | Purpose |
|---|---|
| `sbom_tools.xlsx` | Tool dataset (sheets: SPDXAll, CycloneDXAll, final) |
| `ntia_taxonomy_oss_vs_prop.R` | NTIA taxonomy: open-source vs. proprietary |
| `ntia_taxonomy_spdx_vs_cdx.R` | NTIA taxonomy: SPDX vs. CycloneDX |

### RQ2-tools

| File | Purpose |
|---|---|
| `collect_tool_repo_stats.py` | Collect tool repository statistics (data collection, not re-run) |
| `CycloneNSpdxTools.csv` | Tool repository statistics |
| `main.ipynb` | Returning-contributor commit groups, Mann-Whitney U, Cliff's delta |
| `oss_tools_stats.r` | Community-health statistics |
| `bootstrapping.R` | Bootstrap median with 95% CIs |
| `get_commit_contributor_mapping.py` | Commit counts per contributor |
| `spdx3_adoption_results.csv` | SPDX 3.0 adoption scan |
| `*.pdf`, `*.pkl` | Figures and cached data |

### RQ3-issues

Run order: extraction, content scraping, classification, then analysis.

| Step | Files |
|---|---|
| 1. Extract issues | `issues_extraction.py`, `issues_extraction_chunks.py` → `CdxIssues.csv`, `SpdxIssues.csv` |
| 2. Scrape titles and bodies | `scrape_issue_content.py` → `issues_with_content.csv` |
| 3. Group tags into categories | `splitting_issues_in_tags.py`, `IssuesCategorization.xlsx` |
| 4. Classify with the LLM | `llm_classify_untagged.py` → `llm_classified_issues_devstral-small-2.csv` |
| 5. Deduplicate and assign categories | `build_issue_categories.py` → `CdxIssues_dedup.csv`, `SpdxIssues_dedup.csv`, `issue_categories.csv`, `tag_categories_dedup.csv` |
| 6. Validate against human labels | `sample_issues.csv`, `calculate_krippendorff_alpha.py` |
| 7. Analyze | `issues.R` (counts, resolution time, trend), `tags.R` (category prevalence and resolution time) → `*.pdf`, `cat_diff_by_format.csv` |

### RQ4-project

| File | Purpose |
|---|---|
| `collect_repo_creation_dates.py` | Collect repository creation dates (data collection, not re-run) |
| `all_projects.csv` | All projects found |
| `top250_sampling.R` | Top-250 sampling |
| `scrape_github_metadata.py` | Collect GitHub metadata of sampled projects (data collection, not re-run) |
| `top250_projects.csv` | Sampled projects |
| `language_analysis.ipynb` | GPL/DSL language categories and charts |
| `analysis.ipynb` | Contributor and commit quartiles vs. use cases (chi-square, Pearson residuals) |
| `projects_boxplots.r` | Figures and Mann-Whitney U tests |
| `commit_count_quartile.csv`, `contributor_count_quartile.csv` | Quartile breakdowns |
| `ci_validation_sample94.csv` | Precision check of the CI-config search |

### methodology-figure

`method.pdf` (study method diagram) and `method.pptx` (editable source).

## Environment

| Tool | Requirement |
|---|---|
| Python | Packages in `requirements.txt` |
| R | Required for all `.R`/`.r` scripts; install the packages each script loads |

## Citation

```bibtex
@misc{zhao2025statesbomtoolecosystems,
      title={The State of the SBOM Tool Ecosystems: A Comparative Analysis of SPDX and CycloneDX},
      author={Zhimin Zhao and Abdul Ali Bangash and Tongxu Ge and Arshdeep Singh and Zitao Wang and Bram Adams},
      year={2025},
      eprint={2512.21781},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2512.21781},
}
```
