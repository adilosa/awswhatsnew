import json
import logging
import os
import time
from html.parser import HTMLParser

import boto3
import feedparser
import tweepy
from botocore.client import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


s = MLStripper()


def strip_tags(html):
    s.feed(html)
    return s.get_data()


secret = json.loads(
    boto3.client("s3", config=Config(signature_version="s3v4"))
    .get_object(Bucket=os.environ["bucket"], Key="secrets.json")["Body"]
    .read()
    .decode("utf-8")
)

posts_table = boto3.resource("dynamodb", region_name="us-west-2").Table(
    os.environ["PostsTableName"]
)


def next_limit_reset() -> int:
    response = posts_table.get_item(Key={"guid": "RATE_LIMIT_RESET"})
    if "Item" in response:
        return int(response["Item"]["timestamp"])
    return 0


def already_posted(guid: str) -> bool:
    return "Item" in posts_table.get_item(Key={"guid": guid})


client = tweepy.Client(**secret)

separator = "\n\n"
ellipsis = "... "


def lambda_handler(event, context):
    next_reset_at = next_limit_reset()
    if time.time() < next_reset_at:
        logger.info(
            f"Rate limit reset at {next_reset_at} ({next_reset_at - time.time()}), exiting lambda for now"
        )
        return
    for entry in feedparser.parse("http://aws.amazon.com/new/feed/").entries:
        logger.info(f"Checking {entry.guid} - {entry.title}")
        if not already_posted(entry.guid):
            logger.info(f"Posting {entry.guid} - {entry.title}")
            try:
                char_budget = (
                    280
                    - len(entry.title)
                    - len(entry.link)
                    - len(separator)
                    - len(ellipsis)
                )
                tweet_text = (
                    entry.title
                    + separator
                    + strip_tags(entry.description)[:char_budget]
                    + ellipsis
                    + entry.link
                )
                client.create_tweet(text=tweet_text)
                posts_table.put_item(
                    Item={"guid": entry.guid, "title": entry.title, "link": entry.link}
                )
            except tweepy.TooManyRequests as e:
                response = e.response
                rate_limit_reset = int(response.headers["x-rate-limit-reset"])
                logger.warning(
                    f"Rate limit reached, resetting at {rate_limit_reset}"
                )
                posts_table.put_item(
                    Item={
                        "guid": "RATE_LIMIT_RESET",
                        "timestamp": rate_limit_reset,
                    }
                )
                return
            except Exception:
                logger.exception("Failed to post tweet")
