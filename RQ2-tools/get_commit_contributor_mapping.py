import pandas as pd
import requests
import argparse
import pickle
import re
import os

from collections import defaultdict

# Set up argument parser
parser = argparse.ArgumentParser(description='Fetch and process commit data from GitHub repositories.')
parser.add_argument('token', type=str, help='GitHub personal access token')
args = parser.parse_args()

# Use the provided arguments
GITHUB_TOKEN = args.token
    
script_dir = os.path.dirname(os.path.realpath(__file__))
input_file_path = os.path.join(script_dir, 'CycloneNSpdxTools_with_dates.csv')

# Load the CSV file
df = pd.read_csv(input_file_path)

headers = {'Authorization': f'token {GITHUB_TOKEN}'}

# Function to fetch commits for a repository
def fetch_commits(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/commits'
    commits = []
    page = 1
    while True:
        response = requests.get(url, headers=headers, params={'per_page': 100, 'page': page})
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        commits.extend(data)
        page += 1
    return commits

# Function to get commit counts per contributor
def get_commit_counts(owner, repo):
    commits = fetch_commits(owner, repo)
    commit_counts = defaultdict(int)
    for commit in commits:
        if 'author' in commit and commit['author']:
            author = commit['author']['login']
            commit_counts[author] += 1
    return commit_counts

# Get commit counts for each repository
commit_count_repos = {}
for _, row in df.iterrows():
    owner, repo = row['Repo'].split('/')
    print(f'Processing repository: {owner}/{repo}')
    commit_counts = get_commit_counts(owner, repo)
    commit_count_repos[f'{owner}/{repo}'] = dict(commit_counts)
    
output_file_path = os.path.join(script_dir, 'commit_counts_by_repo.pkl')

# Save the nested dictionary to a pickle file
with open(output_file_path, 'wb') as f:
    pickle.dump(commit_count_repos, f)
