# Data collection step (not re-run): collects tool repository statistics into CycloneNSpdxTools.csv.
# Requires a GitHub token in the GITHUB_TOKEN environment variable.

import pandas as pd
import requests
import time
import os

def get_all_pages(url, headers):
    results = []
    while url:
        response = requests.get(url, headers=headers)
        results.extend(response.json())
        if 'next' in response.links:
            url = response.links['next']['url']
        else:
            url = None
        time.sleep(1)  # To avoid hitting rate limits
    return results

def get_repo_info(repo, token):
    headers = {
        'Authorization': f'token {token}'
    }
    
    base_url = f'https://api.github.com/repos/{repo}'
    
    # Get basic repo information
    repo_info = requests.get(base_url, headers=headers).json()
    
    # Get contributors count
    contributors_url = f'{base_url}/contributors'
    contributors = get_all_pages(contributors_url, headers)
    contributors_count = len(contributors)
    
    # Get open issues count
    open_issues_url = f'{base_url}/issues?state=open'
    open_issues = get_all_pages(open_issues_url, headers)
    open_issues_count = len(open_issues)
    
    # Get closed issues count
    closed_issues_url = f'{base_url}/issues?state=closed'
    closed_issues = get_all_pages(closed_issues_url, headers)
    closed_issues_count = len(closed_issues)
    
    # Get open pull requests count
    open_pulls_url = f'{base_url}/pulls?state=open'
    open_pulls = get_all_pages(open_pulls_url, headers)
    open_pulls_count = len(open_pulls)
    
    # Get closed pull requests count
    closed_pulls_url = f'{base_url}/pulls?state=closed'
    closed_pulls = get_all_pages(closed_pulls_url, headers)
    closed_pulls_count = len(closed_pulls)
    
    # Get releases count
    releases_url = f'{base_url}/releases'
    releases = get_all_pages(releases_url, headers)
    releases_count = len(releases)
    
    # Get total commits count (this endpoint is not paginated, it counts directly)
    commits_url = f'{base_url}/commits'
    commits = get_all_pages(commits_url, headers)
    commits_count = len(commits)
    
    # Get other repository information
    forks_count = repo_info.get('forks_count', 0)
    stargazers_count = repo_info.get('stargazers_count', 0)
    watchers_count = repo_info.get('subscribers_count', 0)
    
    # Compile all information into a dictionary
    info = {
        'CreationDate': repo_info.get('created_at'),
        'Language': repo_info.get('language'),
        'Contributors': contributors_count,
        'OpenIssues': open_issues_count - open_pulls_count,
        'ClosedIssues': closed_issues_count - closed_pulls_count,
        'Commits': commits_count,
        'OpenPullRequest': open_pulls_count,
        'ClosedPullRequest': closed_pulls_count,
        'Releases': releases_count,
        'Forks': forks_count,
        'Stars': stargazers_count,
        'Watchers': watchers_count
    }
    
    return info

token = os.environ['GITHUB_TOKEN']
df = pd.read_csv('CycloneNSpdxTools.csv')
repo_statistics = {}

for index, row in df.iterrows():
    repo = row['link'].split('https://github.com/')[-1]
    if repo not in repo_statistics:
        repo_statistics[repo] = get_repo_info(repo, token)
    for key, value in repo_statistics[repo].items():
        df.at[index, key] = value
    df.to_csv('CycloneNSpdxTools.csv', index=False)
