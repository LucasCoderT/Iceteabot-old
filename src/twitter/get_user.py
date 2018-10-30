import configparser
import os
from pprint import pprint

import timeago
import tweepy

config = configparser.ConfigParser()
config.read(os.path.abspath(os.path.join(__file__, "../../..", "data", "config.ini")))

auth = tweepy.OAuthHandler(config['twitter']['consumer_key'], config['twitter']['consumer_secret'])
auth.set_access_token(config['twitter']['access_key'], config['twitter']['access_secret'])

api = tweepy.API(auth)


def getnewesttweet(username: str):
    """Method to grab the last 20 tweets from a user"""
    user_timeline = api.user_timeline(screen_name=username, count=20)
    # Loops through the last 20 tweets and prints them to the standard output
    for tweet in user_timeline:
        # Checks if the action is a retweet and if it is ignore it
        if tweet.retweeted:
            continue
        else:
            # Outputs the time it was created (UTC) and the text of the tweet
            print(tweet.created_at, tweet.text)


if __name__ == '__main__':
    getnewesttweet('OmniDestiny')
