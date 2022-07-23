import json
import logging
import time
import boto3
from botocore.exceptions import ClientError
import requests

from lambda_basics import LambdaWrapper
from conf import *

logger = logging.getLogger(__name__)


class LambdaCreator:

    def __init__(self):
        self.apig_client = None
        self.api_id = None
        self.lambda_client = None
        self.iam_role = None
        self.wrapper = None
        self.lambda_arn = None
        self.init()

    def init(self):
        """
        Init LambdaWrapper and class arguments
        :return:
        """
        iam_resource = boto3.resource('iam', aws_access_key_id=AWS_ACCESS_KEY,
                                      aws_secret_access_key=AWS_SECRET_KEY)
        self.lambda_client = self.get_aws_client('lambda')
        self.wrapper = LambdaWrapper(self.lambda_client, iam_resource)
        self.iam_role, _ = self.wrapper.create_iam_role_for_lambda(
            LAMBDA_NAME)
        logger.info("Giving AWS time to create resources...")
        time.sleep(10)

    def create_rest_api(self, account_id):
        """
        Creates a REST API in Amazon API Gateway. The REST API is backed by the specified
        AWS Lambda function.

        The following is how the function puts the pieces together, in order:
        1. Creates a REST API in Amazon API Gateway.
        2. Creates a '/demoapi' resource in the REST API.
        3. Creates a method that accepts all HTTP actions and passes them through to
           the specified AWS Lambda function.
        4. Deploys the REST API to Amazon API Gateway.
        5. Adds a resource policy to the AWS Lambda function that grants permission
           to let Amazon API Gateway call the AWS Lambda function.
        :param account_id: The ID of the owning AWS account.
        """
        try:
            response = self.apig_client.create_rest_api(name=API_NAME)
            self.api_id = response['id']
            logger.info("Create REST API %s with ID %s.", API_NAME, self.api_id)
        except ClientError:
            logger.exception("Couldn't create REST API %s.", API_NAME)
            raise

        try:
            response = self.apig_client.get_resources(restApiId=self.api_id)
            root_id = next(
                item['id'] for item in response['items'] if
                item['path'] == '/')
            logger.info("Found root resource of the REST API with ID %s.",
                        root_id)
        except ClientError:
            logger.exception(
                "Couldn't get the ID of the root resource of the REST API.")
            raise

        try:
            response = self.apig_client.create_resource(
                restApiId=self.api_id, parentId=root_id, pathPart=API_BASE_PATH)
            base_id = response['id']
            logger.info("Created base path %s with ID %s.", API_BASE_PATH,
                        base_id)
        except ClientError:
            logger.exception("Couldn't create a base path for %s.",
                             API_BASE_PATH)
            raise

        try:
            self.apig_client.put_method(
                restApiId=self.api_id, resourceId=base_id, httpMethod='ANY',
                authorizationType='NONE')
            logger.info(
                "Created a method that accepts all HTTP verbs for the base "
                "resource.")
        except ClientError:
            logger.exception("Couldn't create a method for the base resource.")
            raise
        lambda_uri = \
            f'arn:aws:apigateway:{self.apig_client.meta.region_name}:' \
            f'lambda:path/2015-03-31/functions/{self.lambda_arn}/invocations'
        try:
            # NOTE: You must specify 'POST' for
            # integrationHttpMethod or this will not work.
            self.apig_client.put_integration(
                restApiId=self.api_id, resourceId=base_id, httpMethod='ANY',
                type='AWS_PROXY',
                integrationHttpMethod='POST', uri=lambda_uri)
            logger.info(
                "Set function %s as integration destination for "
                "the base resource.",
                self.lambda_arn)
        except ClientError:
            logger.exception(
                "Couldn't set function %s as integration destination.",
                self.lambda_arn)
            raise

        try:
            self.apig_client.create_deployment(restApiId=self.api_id,
                                               stageName=API_STAGE)
            logger.info("Deployed REST API %s.", self.api_id)
        except ClientError:
            logger.exception("Couldn't deploy REST API %s.", self.api_id)
            raise

        source_arn = \
            f'arn:aws:execute-api:{self.apig_client.meta.region_name}:' \
            f'{account_id}:{self.api_id}/*/*/{API_BASE_PATH}'
        try:
            self.lambda_client.add_permission(
                FunctionName=self.lambda_arn, StatementId=f'demo-invoke',
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=source_arn)
            logger.info(
                "Granted permission to let Amazon API "
                "Gateway invoke function %s "
                "from %s.", self.lambda_arn, source_arn)
        except ClientError as e:
            if 'already exists' in repr(e):
                ...
            else:
                logger.exception(
                    f"Couldn't add permission to let Amazon "
                    f"API Gateway invoke "
                    f"{self.lambda_arn}. Error: {repr(e)}")
                raise

    def construct_api_url(self):
        """
        Constructs the URL of the REST API.
        :return: The full URL of the REST API.
        """
        region = self.apig_client.meta.region_name
        api_url = \
            f'https://{self.api_id}.execute-api.{region}.amazonaws.com/' \
            f'{API_STAGE}/{API_BASE_PATH}'
        logger.info("Constructed REST API base URL: %s.", api_url)
        return api_url

    def delete_rest_api(self):
        """
        Deletes a REST API and all of its resources from Amazon API Gateway.
        """
        try:
            self.apig_client.delete_rest_api(restApiId=self.api_id)
            logger.info("Deleted REST API %s.", self.api_id)
        except ClientError:
            logger.exception("Couldn't delete REST API %s.", self.api_id)
            raise

    @staticmethod
    def get_aws_client(name):
        return boto3.client(
            name, aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY, region_name='us-east-1')

    def create_lambda(self):

        logging.info(f"Looking for function {LAMBDA_NAME}...")
        function = self.wrapper.get_function(LAMBDA_NAME)
        if function is None:
            logging.info(
                "Zipping the Python script into a deployment package...")
            deployment_package = self.wrapper.create_deployment_package(
                LAMBDA_FILENAME, f"index.py")
            logging.info(f"...and creating the {LAMBDA_NAME} Lambda function.")
            self.lambda_arn = self.wrapper.create_function(
                LAMBDA_NAME, LAMBDA_HANDLER_NAME, self.iam_role,
                deployment_package)
        else:
            logging.info(f"Function {LAMBDA_NAME} already exists.")
            self.lambda_arn = function.get(
                'Configuration', {}).get('FunctionArn')
        logging.info('-' * 88)
        logging.info(f"Deploy dependencies for {LAMBDA_NAME}.")

        if IS_REQUIREMENTS:
            with open('lambda_example/my-package.zip', 'rb') as zip_file:
                self.wrapper.update_function_code(LAMBDA_NAME, zip_file.read())

        logging.info(f"Let's invoke {LAMBDA_NAME}.")
        action_params = {'title': 'Washington,_D.C.'}
        logging.info(f"Invoking {LAMBDA_NAME}...")
        self.wrapper.invoke_function(LAMBDA_NAME, action_params)
        self.wrapper.update_function_configuration(LAMBDA_NAME, Timeout=120)

    def create_api(self):
        logging.info(f"Creating Amazon API Gateway REST API {API_NAME}...")
        self.apig_client = self.get_aws_client('apigateway')
        sts = self.get_aws_client('sts')
        account_id = sts.get_caller_identity()['Account']
        self.create_rest_api(account_id)
        api_url = self.construct_api_url()
        logging.info(f"REST API created, URL is :\n\t{api_url}")
        logging.info(
            f"Sleeping for a couple seconds to give AWS time to prepare...")
        time.sleep(2)

        logging.info(f"Sending some requests to {api_url}...")

        https_response = requests.get(
            api_url,
            params=TEST_PARAMS)
        logging.info(f"REST API returned status {https_response.status_code}\n"
                     f"Message: {json.loads(https_response.text)['message']}")

    def delete_all(self):
        logging.info(
            "Deleting the REST API, AWS Lambda function, and security role...")
        time.sleep(5)  # Short sleep avoids TooManyRequestsException.
        self.wrapper.delete_function(LAMBDA_NAME)
        for pol in self.iam_role.attached_policies.all():
            pol.detach_role(RoleName=self.iam_role.name)
        self.iam_role.delete()
        logging.info(f"Deleted role {self.iam_role.name}.")
        if self.apig_client and self.api_id:
            self.delete_rest_api()

    def run(self):
        """
        Shows how to deploy an AWS Lambda function, create a REST API, call the REST API
        in various ways, and remove all of the resources after the demo completes.
        """
        logging.basicConfig(level=logging.INFO,
                            format='%(levelname)s: %(message)s')
        logging.info('-' * 88)
        logging.info(
            "Welcome to the AWS Lambda and Amazon API Gateway"
            " REST API creation demo.")
        logging.info('-' * 88)

        self.create_lambda()

        if IS_API_CREATE:
            self.create_api()

        if IS_REMOVE:
            self.delete_all()
        logging.info("Thanks for watching!")


if __name__ == '__main__':
    app = LambdaCreator()
    try:
        app.run()
    except KeyboardInterrupt:
        app.delete_all()
