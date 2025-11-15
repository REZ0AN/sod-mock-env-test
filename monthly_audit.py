import asyncio
import aiohttp
import pandas as pd
import sys
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import calendar

BASE_URL="https://api.github.com"

Type = "github-api"
## ensuring if the error.log file exists or not
if not os.path.exists(f'./logs/error/error-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log'):
    with open(f'./logs/error/error-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log', 'w'):
        pass

if not os.path.exists(f'./logs/logs-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log'):
    with open(f'./logs/logs-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log', 'w'):
        pass

## configure logging file
error_logger = logging.getLogger('error_logger')
error_handler = logging.FileHandler(f'./logs/error/error-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

debug_logger = logging.getLogger('debug_logger')
debug_handler = logging.FileHandler(f'./logs/logs-{Type}-{datetime.now().strftime("%Y-%m-%d %H:%M")}.log')
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_handler)
debug_logger.setLevel(logging.DEBUG)


async def get_user_commits(session, config, user):
    """Fetch the commits by a user in a repository."""
    commits = []
    url = f"{BASE_URL}/repos/{config['ORG_NAME']}/{config['REPO_NAME']}/commits"
    params = {
        "author": user,
        "since": config["SINCE"],
        "until": config["UNTIL"]
    }
    print(f"[INFO] Fetching commits for user {user} in repository {config['REPO_NAME']}")
    debug_logger.debug(f'[INFO] Fetching commits for user {user} in repository {config["REPO_NAME"]}')
    
    async with session.get(url, headers=config['HEADERS'], params=params) as response:
        df = pd.DataFrame()
        
        if response.status == 200:
            commits = await response.json()
            if commits == []:
                print(f"[WARNING] {user} may not a contibutor to the repository {config['REPO_NAME']}")
                debug_logger.debug(f'[WARNING] {user} may not a contibutor to the repository {config["REPO_NAME"]}')   
                return df
            for commit in commits:
                commit_data = {
                    'organization_name': config['ORG_NAME'],
                    'repository_name': config['REPO_NAME'],
                    'user': user,
                    'commit_sha': commit['sha'],
                    'commit_date': commit['commit']['author']['date'],
                    'commit_message': commit['commit']['message']
                }
                n_df = pd.DataFrame([commit_data])
                df = pd.concat([df,n_df],ignore_index=True)
            print(f"[SUCCESS] Commits fetched for user {user} in repository {config['REPO_NAME']}")
            debug_logger.debug(f'[SUCCESS] Commits fetched for user {user} in repository {config["REPO_NAME"]}')
            return df
        else:
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"HTTP {response.status}"
            )

async def audit_commits(session, config, users):
    """Audit Commits By username in a repository to a csv file (sequential)."""
    df = pd.DataFrame()

    for user in users:
        try:
            commits = await get_user_commits(session, config, user)
            df = pd.concat([df, commits], ignore_index=True)
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[error] failed to fetch commits for user {user} in repository {config['REPO_NAME']}")
            error_logger.error(
                f"Error occurred while fetching commits for user {user} in repository {config['REPO_NAME']}: {e}"
            )
            continue

    df.drop_duplicates(inplace=True)
    return df



# Save the DataFrame to a CSV file with custom text
def save_csv_with_meta_info(dataframe, filename, meta_info):
    # Open the file in write mode
    with open(filename, 'w') as f:
        # Write the custom text first
        f.write(meta_info)
        
        # Now write the DataFrame to the file
        dataframe.to_csv(f, index=False)

async def process_repository(session, repo, config, usernames):
    """Process a single repository asynchronously"""
    try:    
        # extracting organization name and repository name from the repository link
        ORG_NAME = repo.split("/")[-2]
        REPO_NAME = repo.split("/")[-1].split(".")[0]
        # adding them to config
        repo_config = config.copy()
        repo_config["ORG_NAME"] = ORG_NAME
        repo_config["REPO_NAME"] = REPO_NAME

        # get audit for repo
        df = await audit_commits(session, repo_config, usernames)
        return df

    except Exception as e:
        print(f"[error] failed to audit repository {repo}")
        error_logger.error(f"Error occurred while auditing repository {repo}: {e}")
        return pd.DataFrame()

async def main():
    # Get the usernames passed as an argument
    if len(sys.argv) < 8:
        print(f"[ERROR] program argument not provided expected three argument 1st USERNAMES 2nd MONTH_START 3rd MONTH_END 4th TEAM_NAME 5th is_period 6th PERIOD 7th APPLICATION_NAME")
        error_logger.error("[ERROR] program argument not provided expected three argument 1st USERNAMES 2nd MONTH_START 3rd MONTH_END 4th TEAM_NAME 5th is_period 6th PERIOD 7th APPLICATION_NAME")
        sys.exit(1)

    # extracting the username
    usernames_ = sys.argv[1]
    # extracting the start month
    MONTH_START = sys.argv[2]
    # extracting the end month
    MONTH_END = sys.argv[3]
    # extracting the team_name
    TEAM_NAME = sys.argv[4]
    # extracting the IS_PERIOD
    IS_PERIOD = int(sys.argv[5])
    # extracting the period
    PERIOD = int(sys.argv[6])
    print(f"************************* RUNNING monthly-audit.py for {TEAM_NAME} ********************************")
    # creating datetime object
    start_month = datetime.strptime(MONTH_START, '%Y-%m')
    if IS_PERIOD == 1:
        # get the end month in datetime format
        end_month = start_month - relativedelta(months=PERIOD)
        MONTH_END = end_month.strftime('%Y-%m')
        MONTH_START, MONTH_END = MONTH_END, MONTH_START
        start_month, end_month = end_month, start_month
    else:
        # get the end month in datetime format
        end_month = datetime.strptime(MONTH_END, '%Y-%m')
        MONTH_END = end_month.strftime('%Y-%m')
    
    # Split the string into a list 
    usernames = usernames_.split()

    # get the github access token
    TOKEN = os.environ.get('GH_PAT')
    
    # get the APPLICATION_NAME
    APPLICATION_NAME = sys.argv[7]

    # defining the header for REST-API get request
    HEADERS = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {TOKEN}",
                "X-GitHub-Api-Version": "2022-11-28"
            }
    
    # extracting the first day and last day of the current month
    _, last_day_of_month = calendar.monthrange(end_month.year, end_month.month)
    SINCE = f"{MONTH_START}-01T00:00:00Z"
    UNTIL = f"{MONTH_END}-{last_day_of_month}T23:59:59Z"

    # config dictionary 
    config = {
        "TOKEN":TOKEN,
        "HEADERS":HEADERS,
        "SINCE":SINCE,
        "UNTIL":UNTIL,
    }

    with open(f'./repos.txt') as f:
        repos = f.read().splitlines()

    ## exported data collection
    all_Df = pd.DataFrame()
    print(f"[INFO] Starting audit for {TEAM_NAME} from {MONTH_START} to {MONTH_END}")
    debug_logger.debug(f'[INFO] Starting audit for {TEAM_NAME} from {MONTH_START} to {MONTH_END}')
    
    # Create aiohttp session and process all repositories concurrently
    async with aiohttp.ClientSession() as session:
        for repo in repos:
            df = await process_repository(session, repo, config, usernames)
            all_Df = pd.concat([all_Df, df], ignore_index=True)
            
    filename = f"./audits/{TEAM_NAME}-{MONTH_START}-to-{MONTH_END}-audit.csv"
    # meta info to be added before the header
    meta_info = f'\n\nAudit Report from {MONTH_START} to {MONTH_END}\n\nTeam_Name:{TEAM_NAME}\n\nApplication: {APPLICATION_NAME}\n\n'
    save_csv_with_meta_info(all_Df, filename, meta_info)
    print(f"[SUCCESS] Audit report generated for {TEAM_NAME} from {MONTH_START} to {MONTH_END} in ./audits/{TEAM_NAME}-{MONTH_START}-to-{MONTH_END}-audit.csv")
    debug_logger.debug(f'[SUCCESS] Audit report generated for {TEAM_NAME} from {MONTH_START} to {MONTH_END} in ./audits/{TEAM_NAME}-{MONTH_START}-to-{MONTH_END}-audit.csv')
    print(f"************************* COMPLETED monthly-audit.py for {TEAM_NAME} ********************************")

if __name__ == "__main__":
    asyncio.run(main())