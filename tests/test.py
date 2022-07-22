from datetime import datetime
import unittest
from mock import patch

from monthCount.index import lambda_handler


class TestHandler(unittest.TestCase):
    """
    Test lambda handler
    """
    @patch('monthCount.index.get_latest_update')
    @patch('monthCount.index.get_month_count')
    @patch('monthCount.index.save')
    def test_handler_response(self, mocked_update,
                              mocked_month_count, mocked_save):
        """Test handler main function for successfully response"""
        mocked_update.return_value = \
            datetime.strptime('12:33, 10 May 2022', '%H:%M, %d %B %Y')
        mocked_month_count.return_value = '13'
        mocked_save.return_value = None
        response = lambda_handler({'title': 'Washington,_D.C.'}, None)

        self.assertEqual(200, response['statusCode'])
        self.assertEqual(
            response['body']['message'],
            'File Washington,_D.C..json saved successful.')
