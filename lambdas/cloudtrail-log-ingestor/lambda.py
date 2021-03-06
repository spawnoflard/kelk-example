'''
Based on https://github.com/dbnegative/lambda-cloudfront-log-ingester

MIT License

Original work Copyright (c) 2016 Jason Witting
Modified work Copyright (c) 2017 Steamhaus

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
import os
import gzip
import json
import dateutil.parser
import boto3
import datetime
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection
from elasticsearch import helpers


def parse_log(filename):
    recordset = []

    log = gzip.open(filename, mode='rt')
    records = json.loads(log.readlines()[0])["Records"]

    date = datetime.datetime.today().strftime('%Y-%m-%d')

    for record in records:
        event_time_string = record.pop('eventTime')
        record['eventTime'] = dateutil.parser.parse(event_time_string)
        es_record = {
            "_index": "cloudtrail-logs-" + date,
            "_type": "logs",
            "_source": record
        }
        # append to recordset
        recordset.append(es_record)

    return recordset


def write_bulk(record_set, es_client):
    print("Writing data to ES")
    resp = helpers.bulk(es_client,
                        record_set,
                        chunk_size=1000,
                        timeout="60s")
    return resp


def lambda_handler(event, context):
    auth = BotoAWSRequestsAuth(aws_host=os.environ['ES_HOST'],
                               aws_region=os.environ['ES_REGION'],
                               aws_service='es')

    es_client = Elasticsearch(host=os.environ['ES_HOST'],
                              port=443,
                              use_ssl=True,
                              connection_class=RequestsHttpConnection,
                              http_auth=auth)

    s3_client = boto3.client('s3')

    event_bucket = event['Records'][0]['s3']['bucket']['name']
    event_key = event['Records'][0]['s3']['object']['key']
    downloaded_file_path = '/tmp/cloudtrail_log.gz'
    s3_client.download_file(event_bucket, event_key, downloaded_file_path)

    record_set = parse_log('/tmp/cloudtrail_log.gz')

    resp = write_bulk(record_set, es_client)
    print(resp)
