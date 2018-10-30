import datetime
import praw
import configparser
import os


def getrecentmessages(user: str = "darkkmello", amount: int = 4):
    # Declares the config_file to use
    config = configparser.ConfigParser()
    config.read("{0}/data/config.ini".format(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))
    reddit = praw.Reddit(client_id=config['reddit']['client_id'], client_secret=config['reddit']['client_secret'],
                         password=config['reddit']['password'], user_agent=config['reddit']['user_agent'],
                         username=config['reddit']['username'])
    target_user = reddit.redditor(user)
    return target_user.comments.new(limit=amount)


if __name__ == '__main__':
    tempvar = getrecentmessages()
    print(tempvar)
