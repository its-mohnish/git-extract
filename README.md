# Git Extract

This repository holds a notebook and its equivalent script files to extract developer details from an organizations/user's github profile. It extract information from all public repositories using github's rest endpoints.

# Files

- test_git_details_refactored: A python notebook which extracts github data
- gitExtract: Clone of test_git_details_refactored in py file for use in other script files
- script: A script file which automatically fetches github dev activity for all coins of interest using coingecko API. The details are pushed to a google document available online

# Working

We describe the working of the whole system below

## Getting dev details 

- gitInfo is a class present in gitExtract.py which implements all the endpoints and methods to fetch details. It is initialized with user's email and git token. This is required to fetch information using github API.
- We create a github session initialized with credentials. This session pings all the endpoints.
- All endpoints in github API are paginated. We can fetch a maximum of 100 datapoints within 1 API call
- We first get the general details about the organization/user -> Information about all public repos in fetched. This includes the number of commits, its date of creation, whether its forked or not, and finally whether its archived
- The number of commits are fetched using SOUP library since github does not return this detail.
- Since we get all commits for each and every repo, which can be very time consuming, we get the commits asynchronously. We have a special method called get_data_asynchronous which calls the fetch() method.
- Once we have all commit information for each repo., we extract author details, commit details and plot them in a graph to understand Dev activity
- All this can be done directly from a single function call - run()
- If you are not using this function, check for the code flow. Each method is dependent on some other method. The code flow can be checked from run() function.

## Putting it all into a google doc

- Since running all of this for each and every coin can get quite boring, script.py can automate the whole collection process. Once collected, all details are pushed onto a google doc sequentially for each coin.
- It also puts up each developers activity for a organization into a google sheet which can help us analyze the dev-team commonality between differnt crypto projects
- We use coingecko API to fetch details about each coins github organization name and pass this on to get dev activity
- Once we get the details and plots, we push the plots into google drive, put them into google doc along with all the other details, put dev. details into a google sheet, and delete the plots from the drive to prevent the plot images from occupying all the space on drive
- Please have a look at the code for understanding the proper code flow
