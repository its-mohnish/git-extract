import json
import requests
import pandas as pd
from pandas.io.json import json_normalize
import numpy as np
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from pprint import pprint
import asyncio
from timeit import default_timer
from concurrent.futures import ThreadPoolExecutor
import nest_asyncio
import time
nest_asyncio.apply()
from bs4 import BeautifulSoup
import pickle as pkl
from collections import defaultdict
from datetime import datetime
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

class gitInfo:

  '''
  Instantiate class to connect to github api 

  Parameters
  ---------
  id - mail id for accessing api
  token - token for accessing api
  retry - No. of times the session should retry to connect to github api for each api call
  backoff - backoff factor

  Token can be created through developers option on github website under profile settings
  Sample Token that can be used to access api
  Token 
  -----
  id - mohnish@buyhatke.com 
  token - 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

  Be wary of api limits - 5000 api calls per hour. We can access a maximum of 500000 datapoints in an hour (100 pts per page)
  I retrieve the maximum number of datapoints on each call for optimum results
  '''

  def __init__(self, id, token, retry = 3, backoff = 2):
    self.retry = retry
    self.backoff = backoff
    self.baseUrl = "https://api.github.com"

    self.auth = (id, token)
    self.ghSession = self.createSession()

  def createSession(self):
    try:
      retries = Retry(total = self.retry, backoff_factor = self.backoff)
      ghSession = requests.Session()
      ghSession.mount("https://", HTTPAdapter(max_retries = retries))
      ghSession.auth = self.auth
      return ghSession
    except Exception as e:
      print('Error in creating session :' + e.args[0])

  def getRateLimitLeft(self):
    '''
    Gets no. of api calls that can be made - Max. is 5000 & is refreshed each hour
    '''
    return self.ghSession.get(self.baseUrl + "/rate_limit").json()['rate']['remaining']

  def fetch(self, repo, page):
    '''
      function that retrives commits from each page of a repo - used in tandem with asynchronous method to make it faster
    '''
    url = f"{self.baseUrl}/repos/{repo}/commits?page={page}&per_page=100"
    
    with self.ghSession.get(url) as response:
        data = response.json()
        l = 1
        while response.status_code != 200:
            print("sleep")
            time.sleep(120 * l)
            print("Awake")
            response = self.ghSession.get(url)
            data = response.json()
            l += 1
        return data

  async def get_data_asynchronous(self, repo, nosOfCommits):
    '''
    Asynchronous method to retreive commits for repo. provided
    '''
    page = [i for i in range(1, nosOfCommits//100 + 2)]
    commitList = []

    with ThreadPoolExecutor(max_workers = 4) as executor:     
          dloop = asyncio.get_event_loop()

          tasks = [
              dloop.run_in_executor(
                  executor,
                  self.fetch,
                  *(repo, p) 
              )
              for p in page
          ]
          
          for response in await asyncio.gather(*tasks):
              commitList.append(response)
    
    return commitList

  def getPublicRepos(self, extension):
    '''
    Gets details of an organization
    '''
    response = self.ghSession.get(url = f"{self.baseUrl}{extension}")
    organizationDetails = response.json()
    return organizationDetails

  def findCommitNo(self, repos):
    '''
    Manually getting total commits from each repo. page
    Uses soup directly to parse the page
    '''
    r = requests.get(f"https://github.com/{repos}")
    b = BeautifulSoup(r.content, 'html.parser')
    nosOfCommits = 0

    for x in b.find_all('span', class_ = 'd-none d-sm-inline'):
      if x.find('strong'):
        nosOfCommits = int(''.join(x.find('strong').text.split(',')))    
    
    return nosOfCommits

  def getMaps(self, commitDetails):
    '''
    Simplifies commit details to extract each author's details as well as date-time activity for an organization
    '''
    authorsMap = dict()
    dateMap = defaultdict(int)

    for repo in commitDetails:
      if 'commitList' in commitDetails[repo]:
        for i in commitDetails[repo]['commitList']:
          for x in i:
            temp = x['commit']['author']
            d = temp['date'].split('T')[0]
            key = temp['name']

            if not x['author']:
              link = None
            else:
              link = x['author']['html_url']

            if key not in authorsMap:
              authorsMap[key] = {
                  'commits': 1,
                  'date': defaultdict(int),
                  'link': {link},
                  'repos': defaultdict(int)
              }
              authorsMap[key]['date'][d] += 1
              authorsMap[key]['repos'][repo] += 1
            else:
              authorsMap[key]['commits'] += 1
              authorsMap[key]['date'][d] += 1
              authorsMap[key]['repos'][repo] += 1
              authorsMap[key]['link'].add(link)

            dateMap[d] += 1
    
    return authorsMap, dateMap 

  def getRepoDetails(self, extension):
    '''
    Retrieves each repo. detail from an organization and puts its into a dictionary
    '''

    publicRepos = self.getPublicRepos(extension)['public_repos']

    iterations = publicRepos//100 + 2
    repoDetails = dict()

    #Get 100 repos. details (or max. possible) on a page of an organization
    for page in range(1, iterations):
      response = self.ghSession.get(url = self.baseUrl + f"{extension}/repos?page={page}&per_page=100")
      repos = response.json()
      print(repos)
      for r in repos:
        repoDetails[r['full_name']] = {
            'archived': r['archived'],
            'date': r['created_at'],
            'forked': r['fork']
        }

    return repoDetails
  
  def getCommitDetails(self, repoDetails):
    '''
    Retrieves all commit details for all repos from an organization - Does not do it for forked repos
    '''

    probRepo = {
        'forked': [repo for repo in repoDetails if repoDetails[repo]['forked']], 
        'zero-commit': list()
    }
    repoCount = 0

    for repos in repoDetails:
      repoCount += 1
      
      #If forked, continue
      if repoDetails[repos]['forked']:
        continue
      
      #If issue in getting commits on page, continue
      nosOfCommits = self.findCommitNo(repos)
      if nosOfCommits == 0:
        probRepo['zero-commit'].append(repos)
        continue

      #Define async. event and pass repo. name and commits for it to retrieve
      loop = asyncio.get_event_loop()
      future = asyncio.ensure_future(self.get_data_asynchronous(repos, nosOfCommits))
      commits = loop.run_until_complete(future)
      
      #After retrieving details for 5 repos., sleep to avoid hitting rate limit
      if repoCount%5 == 0:
        time.sleep(5)

      repoDetails[repos]['commitList'] = commits
    
    return repoDetails

  def plotDataMap(self, dateMap, resample = '1W'):
    '''
    Plots date time activity of organization
    '''
    dataDf = json_normalize([{'date': pd.to_datetime(k), 'commits': v} for k,v in dateMap.items()]).sort_values(by = ['date'])
    dataDf = dataDf.resample(resample, on = 'date').sum()
    fig = go.Figure([go.Scatter(x=dataDf.index, y=dataDf['commits'])])
    fig.update_layout(
      title="Commits v/s Time",
      xaxis_title= f"Date resampled on - {resample}",
      yaxis_title="Commits"
      )
    fig.show()

  def authorDetails(self, authorMap, dateMap):
    '''
    Prints out meaningful author details - decorator method
    '''
    sortedAuthorsList = sorted(authorMap.items(), key = lambda x : x[1]['commits'], reverse = True)
    total = sum([authorMap[i]['commits'] for i in authorMap])
    repos = len(set([repo for i in authorMap for repo in authorMap[i]['repos']]))

    print(f"Nos of contributors {len(authorMap)}\nNos of days git has been active {len(dateMap)}\nTotal nos of commits done in {repos} repos. are {total}")
    print("\n" + "-"*50 + "\n")
    
    for author in sortedAuthorsList:
      if author[1]['commits']/total < 0.01:
        print('Others -> ~ 1%')
        break

      print(f"{author[0]} -> {author[1]['commits'] * 100/total} \nGithub Links")  

      for j, l in enumerate(author[1]['link']):
        print(f'\t{j + 1}. {l}')
      
      print('Repos worked on listed below')
      sortedRepoList = sorted(author[1]['repos'].items(), key = lambda x : x[1], reverse = True)
      for j, r in enumerate(sortedRepoList):
        print(f'\t{j + 1}. {r[0].split("/")[1]} -> {r[1]}')
      print("\n" + '-'*20 + "\n")

    return sortedAuthorsList

  def run(self, name, isUser = False):
    '''
    Combines all functions together
    If someone wants the direct results of all methods, they can run this method
    or else, can run individual methods to get more detailed information
    '''
    
    extension = '/orgs/'
    if isUser: extension = '/users/'
    extension += name

    print('Entered')
    repoDetails = self.getRepoDetails(extension)
    print('Done - repo details')
    commitDetails = self.getCommitDetails(repoDetails)
    print('Done - commit Details')
    authorMap, dateMap = self.getMaps(commitDetails)
    print('Done - authormap, dateMap')
    sortedAuthorList = self.authorDetails(authorMap, dateMap)
    print('Done - author details')
    self.plotDataMap(dateMap)
    self.plotDataMap(dateMap, '1Y')