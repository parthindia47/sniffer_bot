# -*- coding: utf-8 -*-
"""
Created on Tue Oct 20 01:00:08 2020

@author: parth pandya

About :
    this file was specifically made to support csv to json converstion for
    twitter list of coins.

"""

import csv
import json
from tweepy import OAuthHandler
import tweepy

#Variables that contains the user credentials to access Twitter API
access_token = "1107323750322565120-DSt623ScZWrEWVHKutoZhKuFVaT4AR"
access_token_secret = "ho2jKpqQDYGvHmYU3xZWLvJi6NcQ0fBBSpV8sGDK7hBlz"
consumer_key = "jjOItHZUspNcY3HxNioQ6cOla"
consumer_secret = "KCKP5dyxn1yd0QgpYDVmdpnUaCfarkRWH0FBPDbaRHv7jcyL58"


# Function to convert a CSV to JSON
# Takes the file paths as arguments
def make_json(csvFilePath, jsonFilePath):
    global api

    # create a dictionary
    try:
        with open(jsonFilePath, 'r+') as openfile:
            data = json.load(openfile)
    except:
        data = {}
        open(jsonFilePath, 'w+')



    # Open a csv reader called DictReader
    with open(csvFilePath, encoding='utf-8') as csvf:
        csvReader = csv.DictReader(csvf)

        # Convert each row into a dictionary
        # and add it to data
        for rows in csvReader:

            # Assuming a column named 'No' to
            # be the primary key
            #del rows['sym']

            try:
                sym = rows["sym"]
                if sym in data:
                    print("already present : " + str(rows) )
                else:
                    user_ID = api.get_user( rows["twitter_userName"] ).id_str
                    rows["id"] = user_ID
                    del rows["sym"]
                    data[ sym ] = rows
                    print("success : " + str(rows) )
            except:
                print("fail : " + str(rows) )
                user_ID = "0"

    # Open a json writer, and use the json.dumps()
    # function to dump data
    with open(jsonFilePath, 'w', encoding='utf-8') as jsonf:
        jsonf.write(json.dumps(data, indent=4))

# Driver Code

#This handles Twitter authetification and the connection to Twitter Streaming API
auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)

# calling the api
api = tweepy.API(auth)

# provide input file and output file.
# input file is simple csv file with coin name and twitter Acc name.
# output file is json file with symbol as key.
csvFilePath = r'list_of_twitter_accounts.csv'
jsonFilePath = r'coin_twitterDB_SymbolAsKey.json'

# Call the make_json function
make_json(csvFilePath, jsonFilePath)
