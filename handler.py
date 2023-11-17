import json
import logging
import os
import time
from html.parser import HTMLParser

import boto3
import feedparser
import twitter
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


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


api = twitter.Api(
    **{
        k: v
        for k, v in json.loads(
            boto3.client("s3", config=Config(signature_version="s3v4"))
            .get_object(Bucket=os.environ["bucket"], Key="secrets.json")["Body"]
            .read()
            .decode("utf-8")
        ).items()
        if k
        in {
            "consumer_key",
            "consumer_secret",
            "access_token_key",
            "access_token_secret",
        }
    }
)

posts_table = boto3.resource("dynamodb", region_name="us-west-2").Table(os.environ["PostsTableName"])


def within(t: time.struct_time, minutes: int) -> bool:
    return abs(time.mktime(time.gmtime()) - time.mktime(t)) <= (minutes * 60)


def already_posted(guid: str) -> bool:
    return "Item" in posts_table.get_item(Key={"guid": guid})


def lambda_handler(event, context):
    for entry in feedparser.parse("http://aws.amazon.com/new/feed/").entries:
        logger.info(f"Checking {entry.guid} - {entry.title}")
        if not already_posted(entry.guid):
            logger.info(f"Posting {entry.guid} - {entry.title}")
            try:
                api.PostUpdate(
                    (entry.title + "\n\n" + strip_tags(entry.description))[:249]
                    + "... "
                    + entry.link,
                    verify_status_length=False,
                )
                posts_table.put_item(
                    Item={"guid": entry.guid, "title": entry.title, "link": entry.link}
                )
            except Exception:
                logger.exception(f"Failed to post tweet")
