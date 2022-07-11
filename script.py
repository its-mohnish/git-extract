import requests
from pprint import pprint
import json
import pandas as pd
from pandas.io.json import json_normalize
import numpy as np
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
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
import gspread
import os
import string

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import json
from pprint import pprint
from googleapiclient.http import MediaFileUpload
import socket

from gitextract import gitInfo

socket.setdefaulttimeout(300)

class coingecko:
	'''
	CLass to connect to the coingecko api
	Functions
	---------
	getTopKCoins: Can get top K coins based on market cap. 
	getCoinOrganization: Returns organization name (for github repo.) of the coin given coin Id
	'''

	def __init__(self):
		self.baseUrl = 'https://api.coingecko.com/api/v3'

	def getTopKCoins(self, topK = 300):
		coinsList = []
		page = 1
		
		while topK:
			try:
				response = requests.get(f'{self.baseUrl}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}&sparkline=false&price_change_percentage=false').json()
				for coins in response:
					if not topK:
						break
					else:
						topK -= 1
						coinsList.append(coins['id'])
				page += 1
			except Exception as e:
				print(e)

		return coinsList

	def getCoinOrganization(self, coinId):
		organizationRepos = list()

		try:
			response = requests.get(f'{self.baseUrl}/coins/{coinId}?localization=false&tickers=false&market_data=false&community_data=false').json()
			for repos in response['links']['repos_url']['github']:
				organizationRepos.append(repos.split('/')[3])
		except Exception as e:
			print(e)

		return set(organizationRepos)


# Converts number to column name for google sheet
def n2a(n,b=string.ascii_uppercase):
  d, m = divmod(n,len(b))
  return n2a(d-1,b)+b[m] if d else b[m]

# Function to upload image to drive
def uploadImg(plotName):
  global driveService

  file_metadata = {'name': plotName}
  media = MediaFileUpload(plotName,
                          mimetype='image/png')
  file = driveService.files().create(body=file_metadata,
                                      media_body=media,
                                      fields = '*').execute()

  print(driveService.permissions().create(fileId = file['id'], body = {'role': 'writer', 'type': 'anyone'}, fields = '*').execute())
  print(driveService.permissions().list(fileId = file['id'], fields = '*').execute())
  
  return file['id']

# Function to delete uploaded image
def deleteImg(fileId):
  global driveService
  driveService.files().delete(fileId = fileId).execute()

# Function to upload data to document
def upload2Doc(data, idx):
  global DOCUMENT_IDS, PLOT_NAMES, docService, driveService

  # upload image
  imgId1 = uploadImg(PLOT_NAMES[0])
  imgId2 = uploadImg(PLOT_NAMES[1])
  
  requests = [
  {
      'insertText': {
          'location': {
              'index': idx - 1,
          },
          'text': data[0]
      }
  },
  {
      'insertText': {
          'location': {
              'index': idx - 1,
          },
          'text': '\n'
      }
  },
  {
      'insertInlineImage': {
          'uri': 'https://drive.google.com/uc?id='+imgId1+'&export=view',
          'location': {
              'index': idx - 1
          }
      }
  },
  {
      'insertText': {
          'location': {
              'index': idx - 1,
          },
          'text': '\n'
      }
  },
  {
      'insertInlineImage': {
          'uri': 'https://drive.google.com/uc?id='+imgId2+'&export=view',
          'location': {
              'index': idx - 1
          }
      }
  },
  {
      'insertText': {
        'location':{
          'index': idx - 1,
        },
        'text': data[1]
      }
  },
  {
      'updateTextStyle':{
        'textStyle':{
          'bold': True
        },
        'fields': 'bold',
        'range': {
          'startIndex': idx - 1,
          'endIndex': idx + len(data[1]) - 2
        }
      }
  },
  {
      'insertPageBreak': {
          'location': {
              'index': idx - 1
          }
      }
  }
  ]

  # perform request
  result = docService.documents().batchUpdate(documentId=DOCUMENT_IDS[0], body={'requests': requests}).execute()
  
  # delete uploaded image to free space
  deleteImg(imgId1)
  deleteImg(imgId2)

  return idx + len(data[0]) + len(data[1]) + 7


if __name__ == '__main__':
  
  # Defining final variables for automatization
  THRESHOLD = 0.005
  COINS = 1000
  DOCUMENT_IDS = ['1Ym2xIscH5H9GPUqnMGzDjvgRxLKZ1WngqrIZd8mQntI', '1tAaWjnY0lNW9HppUM9B2Ojb6Ux_w-ywet1fOWcPR0ho']
  PLOT_NAMES = ['plot1.png', 'plot2.png']
  CREDENTIALS = {
    'id': 'mohnish@buyhatke.com',
    'token': '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'
  }
  CONFIG_PATH = os.path.dirname(os.path.realpath(__file__)) + "/config.json"

  # Get coin details from coingecko api
  coingeckoObj = coingecko()
  coinList = coingeckoObj.getTopKCoins(COINS)
  gitObj = gitInfo(**CREDENTIALS)

  # Open google doc. for automatization
  creds = service_account.Credentials.from_service_account_file(CONFIG_PATH)
  try:
    docService = build('docs', 'v1', credentials = creds)
    driveService = build('drive', 'v3', credentials = creds)
    document = docService.documents().get(documentId = DOCUMENT_IDS[0]).execute()
    idx = document.get('body').get('content')[-2]['startIndex']
  except HttpError as err:
    print(err)

  # Open google sheet for contributor graph
  gc = gspread.service_account(CONFIG_PATH)
  sh = gc.open_by_url(f'https://docs.google.com/spreadsheets/d/{DOCUMENT_IDS[1]}').sheet1
  contributorsFromSheet = sh.col_values(1)
  links = sh.col_values(2)
  headers = sh.row_values(1)

  # Start fetching and uploading details to document and sheet
  for id_ in coinList:
    print(id_)
    org = coingeckoObj.getCoinOrganization(id_)
    contributors = dict()

    for o in org:
      print(o)
      repoDetails = gitObj.getRepoDetails(o)
      commitDetails = gitObj.getCommitDetails(repoDetails)
      authorMap, dateMap = gitObj.getMaps(commitDetails)
      fig1 = gitObj.plotDataMap(dateMap)
      fig2 = gitObj.plotDataMap(dateMap, '1Y')
      fig1.write_image(PLOT_NAMES[0])
      fig2.write_image(PLOT_NAMES[1])
      total = sum([authorMap[i]['commits'] for i in authorMap])
      repos = len(set([repo for i in authorMap for repo in authorMap[i]['repos']]))


      totalCommits = 0

      for contri in authorMap:
        totalCommits += authorMap[contri]['commits']
        if contri in contributors:
          contributors[contri][0] += authorMap[contri]['commits']
        else:
          if None in authorMap[contri]['link']:
            authorMap[contri]['link'].remove(None)
          contributors[contri] = [authorMap[contri]['commits'], list(authorMap[contri]['link'])]

    details = [f'Nos of contributors {len(authorMap)}\nNos of days git has been active {len(dateMap)}\nTotal nos of commits done in {repos} repos. are {total}',
                f'{id_.upper()}\n'
              ]
    idx = upload2Doc(details, idx)
    
    output = [0]*len(contributorsFromSheet)
    output[0] = id_

    for contri in contributors:
      if contributors[contri][0]/totalCommits > THRESHOLD:
        if contri in contributorsFromSheet:
          output[contributorsFromSheet.index(contri)] = contributors[contri][0]
        else:
          contributorsFromSheet.append(contri)
          output.append(contributors[contri][0])
          links.append(', '.join(contributors[contri][1]))

    if id_ in headers:
      column = n2a(headers.index(id_))
    else:
      column = n2a(len(headers))
      headers.append(id_)

    sh.update(f'A1:A{len(contributorsFromSheet)}', [[i] for i in contributorsFromSheet])
    sh.update(f'B1:B{len(links)}', [[i] for i in links])
    sh.update(f'{column}1:{column}{len(output)}', [[i] for i in output])

    print('-'*50)
    break