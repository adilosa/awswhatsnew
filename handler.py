import os
import json
import xml.etree.ElementTree as ET

import requests
import boto3
from botocore.client import Config
import twitter


def news_items(xml):
    return ET.ElementTree(ET.fromstring(xml)).getroot().find('channel').findall('item')


def lambda_handler(event, context):
    obj = boto3.resource('s3').Object(os.environ['bucket'], 'news.rss')
    new_xml = requests.get("http://aws.amazon.com/new/feed/").text
    try:
        old = set([item.find('guid').text for item in news_items(obj.get()['Body'].read().decode('utf-8'))])
    except:
        print("Failed to read old items")
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
                api.PostUpdate(item.find('title').text[:254] + ' ' + item.find('link').text)
                count += 1
            except:
                print("Failed to post tweet")

    obj.put(Body=new_xml)
    return f"Published {count} tweets"
