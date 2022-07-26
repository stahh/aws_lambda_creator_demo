from datetime import datetime
import unittest
from mock import patch, MagicMock
import json
import sys
sys.path.extend(['../../', '../', './'])

from lambda_example import index

DT = datetime.strptime('12:33, 10 May 2022', '%H:%M, %d %B %Y')
LU = '00:48, 23 July 2022'
MC = '15'
S1 = 'wiki'
S2 = 'xtools'


class TestHandler(unittest.TestCase):
    """
    Test lambda handler
    """

    @staticmethod
    def read(fname):
        with open(fname, 'r') as inp:
            return inp.read()

    @patch('lambda_example.index._get')
    def test_request(self, mocked_get):
        mocked_get.return_value = LU
        wiki = index._get(
            'https://en.wikipedia.org/w/index.php', S1,
            {'title': 'Washington,_D.C.', 'action': 'history'})
        self.assertEqual(LU, wiki)
        mocked_get.return_value = MC
        xtools = index._get(
            'https://xtools.wmflabs.org/articleinfo/en.wikipedia.org/'
            'Washington,_D.C./2022-07-01/2022-07-23#month-counts', S2)
        self.assertEqual(MC, xtools)

    @patch('lambda_example.index.get_latest_update',
           MagicMock(return_value=DT))
    @patch('lambda_example.index.get_month_count', MagicMock(return_value=13))
    @patch('lambda_example.index.save', MagicMock(return_value=None))
    def test_response(self):
        """Test handler main function for successfully response"""
        response = index.lambda_handler(
            {'queryStringParameters': {'title': 'Washington,_D.C.'}}, None)
        self.assertEqual(200, response['statusCode'])
        self.assertEqual(
            json.loads(response['body'])['message'],
            f'File Washington,_D.C..json saved successful. '
            f'Latest update: {DT}. '
            f'Month counts: 13')

    def test_parsing(self):
        wiki = index.parse(self.read(f'{S1}.html'), S1)
        self.assertEqual(LU, wiki)
        xtools = index.parse(self.read(f'{S2}.html'), S2)
        self.assertEqual(MC, xtools)


if __name__ == "__main__":
    unittest.main()
