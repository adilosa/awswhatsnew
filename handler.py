import os
import json
import xml.etree.ElementTree as ET

from html.parser import HTMLParser

import requests
import boto3
from botocore.client import Config
import twitter


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


def news_items(xml):
    return ET.ElementTree(ET.fromstring(xml)).getroot().find('channel').findall('item')


def lambda_handler(event, context):
    obj = boto3.resource('s3').Object(os.environ['bucket'], 'news.rss')
    new_xml = requests.get("http://aws.amazon.com/new/feed/").text
    try:
        old = set(
            [
                item.find('guid').text
                for item in news_items(
                    obj.get()['Body'].read().decode('utf-8')
                )
            ]
        )
    except Exception as e:
        print("Failed to read old items")
        print(e)
        old = set()

    secrets = json.loads(
        boto3.client(
            's3', config=Config(signature_version='s3v4')
        ).get_object(
            Bucket=os.environ['bucket'], Key='secrets.json'
        )['Body'].read().decode('utf-8')
    )

    api = twitter.Api(
        consumer_key=secrets['consumer_key'],
        consumer_secret=secrets['consumer_secret'],
        access_token_key=secrets['access_token_key'],
        access_token_secret=secrets['access_token_secret']
    )

    count = 0
    for item in news_items(new_xml):
        if item.find('guid').text not in old:
            try:
                api.PostUpdate(
                    (
                        strip_tags(item.find('title').text) + '\n\n' +
                        strip_tags(item.find('description').text)
                    )[:249] + '... ' + item.find('link').text,
                    verify_status_length=False
                )
                count += 1
            except Exception as e:
                print("Failed to post tweet")
                print(e)

    obj.put(Body=new_xml)

    return f"Published {count} tweets"
