# Data collection step (not re-run): collects GitHub metadata of the sampled projects into top250_projects.csv.
# Requires a GitHub token in the GITHUB_TOKEN environment variable.

import pandas as pd
import requests
import time
import concurrent.futures
import json
import os
import re
from tqdm import tqdm

class GitHubDataCollector:
    def __init__(self, token, cache_file='github_cache.json'):
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.graphql_headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
    
    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f)
    
    def _check_rate_limit(self):
        """Check and wait if we're approaching rate limit"""
        if self.rate_limit_remaining < 10:
            wait_time = max(0, self.rate_limit_reset - time.time()) + 5
            print(f"Rate limit almost reached. Waiting {wait_time:.0f} seconds...")
            time.sleep(wait_time)
    
    def _update_rate_limit(self, response):
        """Update rate limit info from response headers"""
        if 'X-RateLimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
            self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])
    
    def get_contributors_count(self, repo):
        """Get contributor count using REST API"""
        owner, name = repo.split('/')
        url = f"https://api.github.com/repos/{owner}/{name}/contributors"
        
        # Use pagination to get total count
        response = requests.get(url, headers=self.headers, params={"per_page": 1})
        self._update_rate_limit(response)
        
        if response.status_code != 200:
            print(f"Error fetching contributors for {repo}: {response.status_code}")
            return 0
        
        # Check if we have Link header for pagination
        if 'Link' in response.headers:
            link_header = response.headers['Link']
            last_page_match = re.search(r'page=(\d+)>; rel="last"', link_header)
            if last_page_match:
                return int(last_page_match.group(1))
        
        # If no pagination or fewer contributors than per_page
        return len(response.json())
    
    def get_repo_info_graphql(self, repo):
        """Get repository info using GraphQL API (much more efficient)"""
        if repo in self.cache:
            return self.cache[repo]
        
        owner, name = repo.split('/')
        
        # Revised GraphQL query that doesn't request collaborators information
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            createdAt
            diskUsage
            primaryLanguage { name }
            languages(first: 10) { totalCount edges { size node { name } } }
            openIssues: issues(states: OPEN) { totalCount }
            closedIssues: issues(states: CLOSED) { totalCount }
            openPullRequests: pullRequests(states: OPEN) { totalCount }
            closedPullRequests: pullRequests(states: CLOSED) { totalCount }
            releases { totalCount }
            defaultBranchRef { target { ... on Commit { history { totalCount } } } }
            forkCount
            stargazerCount
            watchers { totalCount }
          }
        }
        """
        
        variables = {"owner": owner, "name": name}
        data = {"query": query, "variables": variables}
        
        self._check_rate_limit()
        response = requests.post('https://api.github.com/graphql', 
                                json=data, 
                                headers=self.graphql_headers)
        
        if response.status_code != 200:
            print(f"Error fetching {repo}: {response.status_code} {response.text}")
            return {}
        
        result = response.json()
        
        if 'errors' in result:
            print(f"GraphQL errors for {repo}: {result['errors']}")
            # We'll continue anyway and just use what we can get
        
        if 'data' not in result or 'repository' not in result['data'] or result['data']['repository'] is None:
            print(f"No repository data returned for {repo}")
            return {}
            
        repo_data = result['data']['repository']
        
        # Extract and format the data
        languages_data = {}
        if repo_data.get('languages') and 'edges' in repo_data['languages']:
            for edge in repo_data['languages']['edges']:
                languages_data[edge['node']['name']] = edge['size']
        
        # Get contributors count using REST API as a fallback
        contributors_count = self.get_contributors_count(repo)
        
        info = {
            'creation_date': repo_data.get('createdAt'),
            'size': repo_data.get('diskUsage'),
            'language': repo_data.get('primaryLanguage', {}).get('name') if repo_data.get('primaryLanguage') else None,
            'LOC': languages_data,
            'contributors': contributors_count,
            'openIssues': repo_data.get('openIssues', {}).get('totalCount', 0) if repo_data.get('openIssues') else 0,
            'closedIssues': repo_data.get('closedIssues', {}).get('totalCount', 0) if repo_data.get('closedIssues') else 0,
            'commits': repo_data.get('defaultBranchRef', {}).get('target', {}).get('history', {}).get('totalCount', 0) 
                      if repo_data.get('defaultBranchRef') and repo_data.get('defaultBranchRef', {}).get('target') else 0,
            'openPRs': repo_data.get('openPullRequests', {}).get('totalCount', 0) if repo_data.get('openPullRequests') else 0,
            'closedPRs': repo_data.get('closedPullRequests', {}).get('totalCount', 0) if repo_data.get('closedPullRequests') else 0,
            'releases': repo_data.get('releases', {}).get('totalCount', 0) if repo_data.get('releases') else 0,
            'forks': repo_data.get('forkCount', 0),
            'stars': repo_data.get('stargazerCount', 0),
            'watchers': repo_data.get('watchers', {}).get('totalCount', 0) if repo_data.get('watchers') else 0
        }
        
        # Cache the results
        self.cache[repo] = info
        self._save_cache()
        
        return info
    
    def process_repositories(self, repos, max_workers=3):
        """Process multiple repositories concurrently"""
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all repositories for processing
            future_to_repo = {
                executor.submit(self.get_repo_info_graphql, repo): repo 
                for repo in repos if repo
            }
            
            # Process as they complete
            for future in tqdm(concurrent.futures.as_completed(future_to_repo), 
                              total=len(future_to_repo),
                              desc="Processing repositories"):
                repo = future_to_repo[future]
                try:
                    results[repo] = future.result()
                except Exception as e:
                    print(f"Error processing {repo}: {str(e)}")
                    results[repo] = {}
        
        return results

# Usage
token = os.environ['GITHUB_TOKEN']
collector = GitHubDataCollector(token)

# Load your CSV
df = pd.read_csv('top250_projects.csv')

# Extract repo names from links
repos = [link.split('https://github.com/')[-1] if isinstance(link, str) and 'github.com' in link else None 
         for link in df['link']]
repos = [r for r in repos if r]  # Filter out None values

# Process repositories
results = collector.process_repositories(repos, max_workers=3)  # Adjust workers as needed

# Update the dataframe with results
for index, row in df.iterrows():
    if isinstance(row['link'], str) and 'github.com' in row['link']:
        repo = row['link'].split('https://github.com/')[-1]
        if repo in results:
            for key, value in results[repo].items():
                df.at[index, key] = value if not isinstance(value, dict) else json.dumps(value)

# Save the updated dataframe
df.to_csv('top250_projects.csv', index=False)
os.remove('github_cache.json')
