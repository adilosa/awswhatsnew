import json
import logging
import os
import re
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
        super().__init__(convert_charrefs=True)
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)



def strip_tags(html):
    s = MLStripper()
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
ellipsis = "..."
url_pattern = re.compile(r"https?://\S+")


def lambda_handler(event, context):
    next_reset_at = next_limit_reset()
    if time.time() < next_reset_at:
        logger.info(
            f"Rate limit reset at {next_reset_at} ({next_reset_at - time.time()}), exiting lambda for now"
        )
        return
    for entry in feedparser.parse("http://aws.amazon.com/new/feed/").entries:
        if not already_posted(entry.guid):
            logger.info(f"Posting {entry.guid} - {entry.title}")
            try:
                # no link: X bills posts containing a URL at ~13x the plain rate
                char_budget = 280 - len(entry.title) - len(separator)
                description = url_pattern.sub("", strip_tags(entry.description)).strip()
                if len(description) > char_budget:
                    description = (
                        description[: char_budget - len(ellipsis)].rstrip() + ellipsis
                    )
                tweet_text = entry.title + separator + description
                client.create_tweet(text=tweet_text)
                posts_table.put_item(
                    Item={"guid": entry.guid, "title": entry.title, "link": entry.link}
                )
                return
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
            except tweepy.HTTPException as e:
                if e.response is not None and e.response.status_code == 402:
                    logger.error("X API credits depleted, exiting lambda for now")
                    return
                logger.exception("Failed to post tweet")
            except Exception:
                logger.exception("Failed to post tweet")
