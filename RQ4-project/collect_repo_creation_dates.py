# Data collection step (not re-run): collects repository creation dates for all_projects.csv.
# Requires a GitHub token in the GITHUB_TOKEN environment variable.

import os
import pandas as pd
from selenium.webdriver.common.by import By
from seleniumbase import Driver

import requests
import time

def get_repo_created_at(repo, token):
    headers = {
        'Authorization': f'token {token}'
    }
    
    base_url = f'https://api.github.com/repos/{repo}'
    
    info = requests.get(base_url, headers=headers).json()
    return info.get('created_at')

driver = Driver(uc=True)
driver.implicitly_wait(5)
driver.get('https://github.com')
time.sleep(30)

df_project = pd.read_csv('all_projects.csv')
token = os.environ['GITHUB_TOKEN']
repo_statistics = {}

for index, row in df_project.iterrows():
    if index < 2119:
        continue
    
    repo = row['repo_link'].split('https://github.com/')[-1]
    
    if repo not in repo_statistics:
        info = {}
        driver.get(row['repo_link'])
        
        try:
            info['commit_count'] = int(driver.find_element(By.XPATH, '//span[@class="Text-sc-17v1xeu-0 gPDEWA fgColor-default"]').text.split(' ')[0].replace(',', ''))
        except:
            print(f'Error: {repo}')
            continue
        
        try:
            contributor_count = driver.find_elements(By.XPATH, f'//a[@href="/{repo}/graphs/contributors"]/span')[0].text
            if contributor_count == '5,000+':
                contributor_count = driver.find_elements(By.XPATH, f'//a[@href="/{repo}/graphs/contributors"]/span')[1].text
                contributor_count = contributor_count.split(' ')[1]
            info['contributor_count'] = int(contributor_count.replace(',', ''))
        except:
            info['contributor_count'] = 1
            
        info['created_at'] = get_repo_created_at(repo, token)    
        print(repo, info)
        repo_statistics[repo] = info
    
    df_project.at[index, 'commit_count'] = repo_statistics[repo]['commit_count']
    df_project.at[index, 'contributor_count'] = repo_statistics[repo]['contributor_count']
    df_project.at[index, 'created_at'] = repo_statistics[repo]['created_at']
    df_project.to_csv('all_projects.csv', index=False)
    time.sleep(1)

driver.quit()
