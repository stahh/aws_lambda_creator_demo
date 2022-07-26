import json
import logging
from datetime import datetime

import boto3
import requests
from bs4 import BeautifulSoup
from multiprocessing import current_process

logger = logging.getLogger(current_process.__name__)
logger.setLevel(logging.INFO)


def parse(page, source):
    """
    Parse given page and return result
    :param page: string: page text
    :param source: string: 'wiki' or 'xtools'
    :return: parsed result
    """
    soup = BeautifulSoup(page, "html.parser")
    if source == 'wiki':
        return soup.find_all(class_="mw-changeslist-date")[0].contents[0]
    else:
        section = soup.find('section', {'id': 'month-counts'})
        for i in section.find_all('tr'):
            col = i.find("td", {'class': 'sort-entry--edits'})
            if col:
                value = col.attrs.get("data-value", None)
                return value


def _get(url, source, params=None):
    """
    Make request to given URL
    :param url: string: URL to request
    :param source: string: 'wiki' or 'xtools'
    :param params: dict: GET parameters
    :return: parsed result
    """
    logger.info(f'Get page {url}, params: {params}')
    response = requests.get(
        url, params=params, headers={
            'User-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/'
                          '537.36 (KHTML, like Gecko) Chrome/103.0.0.0 '
                          'Safari/537.36'}, timeout=60)
    return parse(response.text, source)


def save(title, date, month_count):
    """
    Write JSON file to S3 bucket
    :param title: string: wiki page title
    :param date: datetime: latest update time
    :param month_count: int: edits count for month
    :return: None
    """
    file_name = '{}.json'.format(title)
    bucket_name = 'lambda-demo'
    data = {'number_updates_last_month': month_count,
            'latest_update_time': date.isoformat()}
    logger.info(data)
    s3_client = boto3.client('s3')
    s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=json.dumps(data))


def get_latest_update(title):
    """
    Get latest update time
    :param title: string: wiki page title
    :return: datetime: latest update time
    """
    params = {'title': title, 'action': 'history'}
    return datetime.strptime(
        _get('https://en.wikipedia.org/w/index.php', 'wiki', params),
        '%H:%M, %d %B %Y')


def get_month_count(title, last_date):
    """
    Get edits count for month
    :param title: string: wiki page title
    :param last_date: datetime: latest update time
    :return: int: edits count
    """
    end_date = last_date.date()
    start_date = end_date.replace(day=1)
    return _get(
        'https://xtools.wmflabs.org/articleinfo/en.wikipedia.org/{}/{}/{}'
        '#month-counts'.format(title, start_date, end_date), 'xtools')


def lambda_handler(event, context):
    """
    Entry point method.
    Check params
    Get latest update time
    Get edits count
    Save json file
    :param event: object: lambda event
    :param context: object: lambda context
    :return: dict: status code and message
    """
    logger.info(event.get('queryStringParameters'))
    query_string = event.get('queryStringParameters')
    if not query_string:
        resp = {'statusCode': 400,
                'body': json.dumps({'message': 'ERROR : Bad Request'
                                               '(Missing query parameters).'})}
        return resp
    title = query_string.get('title')
    if not title:
        resp = {'statusCode': 400,
                'body': json.dumps({'message': 'ERROR : Bad Request'
                                               '(Missing title).'})}
        return resp
    title = title.strip()
    try:
        last_date = get_latest_update(title)
        logger.info(f'Latest update: {last_date}')
        month_count = get_month_count(title, last_date)
        logger.info(f'Month count: {month_count}')
        save(title, last_date, month_count)
    except Exception as e:
        logging.error(e)
        resp = {'statusCode': 500,
                'body': json.dumps({'message': f'ERROR : {e}'})}
        return resp

    resp = {
        'statusCode': 200,
        'body': json.dumps({'message': f'File {title}.json saved successful. '
                            f'Latest update: {last_date}. '
                            f'Month counts: {month_count}'})
    }

    return resp


if __name__ == '__main__':
    a = lambda_handler(
        {'queryStringParameters': {'title': 'Washington,_D.C.'}}, None)
    print(a)
