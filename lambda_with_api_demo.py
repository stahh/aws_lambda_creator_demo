import json
import logging
import time
import boto3
from botocore.exceptions import ClientError
import requests

from lambda_basics import LambdaWrapper
from conf import *

logger = logging.getLogger(__name__)


def create_rest_api(
        apigateway_client, account_id, lambda_client, lambda_function_arn):
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

    :param apigateway_client: The Boto3 Amazon API Gateway client object.
    :param api_name: The name of the REST API.
    :param api_base_path: The base path part of the REST API URL.
    :param api_stage: The deployment stage of the REST API.
    :param account_id: The ID of the owning AWS account.
    :param lambda_client: The Boto3 AWS Lambda client object.
    :param lambda_function_arn: The Amazon Resource Name (ARN) of the AWS Lambda
                                function that is called by Amazon API Gateway to
                                handle REST requests.
    :return: The ID of the REST API. This ID is required by most Amazon API Gateway
             methods.
    """
    try:
        response = apigateway_client.create_rest_api(name=API_NAME)
        api_id = response['id']
        logger.info("Create REST API %s with ID %s.", API_NAME, api_id)
    except ClientError:
        logger.exception("Couldn't create REST API %s.", API_NAME)
        raise

    try:
        response = apigateway_client.get_resources(restApiId=api_id)
        root_id = next(
            item['id'] for item in response['items'] if item['path'] == '/')
        logger.info("Found root resource of the REST API with ID %s.", root_id)
    except ClientError:
        logger.exception(
            "Couldn't get the ID of the root resource of the REST API.")
        raise

    try:
        response = apigateway_client.create_resource(
            restApiId=api_id, parentId=root_id, pathPart=API_BASE_PATH)
        base_id = response['id']
        logger.info("Created base path %s with ID %s.", API_BASE_PATH, base_id)
    except ClientError:
        logger.exception("Couldn't create a base path for %s.", API_BASE_PATH)
        raise

    try:
        apigateway_client.put_method(
            restApiId=api_id, resourceId=base_id, httpMethod='ANY',
            authorizationType='NONE')
        logger.info(
            "Created a method that accepts all HTTP verbs for the base "
            "resource.")
    except ClientError:
        logger.exception("Couldn't create a method for the base resource.")
        raise
    lambda_uri = \
        f'arn:aws:apigateway:{apigateway_client.meta.region_name}:' \
        f'lambda:path/2015-03-31/functions/{lambda_function_arn}/invocations'
    try:
        # NOTE: You must specify 'POST' for
        # integrationHttpMethod or this will not work.
        apigateway_client.put_integration(
            restApiId=api_id, resourceId=base_id, httpMethod='ANY',
            type='AWS_PROXY',
            integrationHttpMethod='POST', uri=lambda_uri)
        logger.info(
            "Set function %s as integration destination for the base resource.",
            lambda_function_arn)
    except ClientError:
        logger.exception(
            "Couldn't set function %s as integration destination.",
            lambda_function_arn)
        raise

    try:
        apigateway_client.create_deployment(restApiId=api_id,
                                            stageName=API_STAGE)
        logger.info("Deployed REST API %s.", api_id)
    except ClientError:
        logger.exception("Couldn't deploy REST API %s.", api_id)
        raise

    source_arn = \
        f'arn:aws:execute-api:{apigateway_client.meta.region_name}:' \
        f'{account_id}:{api_id}/*/*/{API_BASE_PATH}'
    try:
        lambda_client.add_permission(
            FunctionName=lambda_function_arn, StatementId=f'demo-invoke',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=source_arn)
        logger.info(
            "Granted permission to let Amazon API Gateway invoke function %s "
            "from %s.", lambda_function_arn, source_arn)
    except ClientError as e:
        if 'already exists' in repr(e):
            ...
        else:
            logger.exception(
                f"Couldn't add permission to let Amazon API Gateway invoke "
                f"{lambda_function_arn}. Error: {repr(e)}")
            raise

    return api_id


def construct_api_url(api_id, region):
    """
    Constructs the URL of the REST API.

    :param api_id: The ID of the REST API.
    :param region: The AWS Region where the REST API was created.
    :param api_stage: The deployment stage of the REST API.
    :param api_base_path: The base path part of the REST API.
    :return: The full URL of the REST API.
    """
    api_url = \
        f'https://{api_id}.execute-api.{region}.amazonaws.com/' \
        f'{API_STAGE}/{API_BASE_PATH}'
    logger.info("Constructed REST API base URL: %s.", api_url)
    return api_url


def delete_rest_api(apigateway_client, api_id):
    """
    Deletes a REST API and all of its resources from Amazon API Gateway.

    :param apigateway_client: The Boto3 Amazon API Gateway client.
    :param api_id: The ID of the REST API.
    """
    try:
        apigateway_client.delete_rest_api(restApiId=api_id)
        logger.info("Deleted REST API %s.", api_id)
    except ClientError:
        logger.exception("Couldn't delete REST API %s.", api_id)
        raise


def get_aws_client(name):
    return boto3.client(
        name, aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY, region_name='us-east-1')


def usage_demo():
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
    apig_client, api_id = None, None

    iam_resource = boto3.resource('iam', aws_access_key_id=AWS_ACCESS_KEY,
                                  aws_secret_access_key=AWS_SECRET_KEY)
    lambda_client = get_aws_client('lambda')
    wrapper = LambdaWrapper(lambda_client, iam_resource)
    iam_role, should_wait = wrapper.create_iam_role_for_lambda(LAMBDA_NAME)
    if should_wait:
        logger.info("Giving AWS time to create resources...")
        time.sleep(10)
    logging.info(f"Looking for function {LAMBDA_NAME}...")
    function = wrapper.get_function(LAMBDA_NAME)
    if function is None:
        logging.info("Zipping the Python script into a deployment package...")
        deployment_package = wrapper.create_deployment_package(
            LAMBDA_FILENAME, f"index.py")
        logging.info(f"...and creating the {LAMBDA_NAME} Lambda function.")
        lambda_arn = wrapper.create_function(
            LAMBDA_NAME, LAMBDA_HANDLER_NAME, iam_role,
            deployment_package)
    else:
        logging.info(f"Function {LAMBDA_NAME} already exists.")
        lambda_arn = function.get('Configuration', {}).get('FunctionArn')
    logging.info('-' * 88)
    logging.info(f"Deploy dependencies for {LAMBDA_NAME}.")

    if IS_REQUIREMENTS:
        with open('lambda_example/my-package.zip', 'rb') as zip_file:
            wrapper.update_function_code(LAMBDA_NAME, zip_file.read())

    logging.info(f"Let's invoke {LAMBDA_NAME}.")
    action_params = {'title': 'Washington,_D.C.'}
    logging.info(f"Invoking {LAMBDA_NAME}...")
    wrapper.invoke_function(LAMBDA_NAME, action_params)

    wrapper.update_function_configuration(LAMBDA_NAME, Timeout=120)

    if IS_API_CREATE:
        logging.info(f"Creating Amazon API Gateway REST API {API_NAME}...")
        apig_client = get_aws_client('apigateway')
        sts = get_aws_client('sts')
        account_id = sts.get_caller_identity()['Account']
        api_id = create_rest_api(apig_client, account_id,
                                 lambda_client, lambda_arn)
        api_url = construct_api_url(api_id, apig_client.meta.region_name)
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

    if IS_REMOVE:
        logging.info(
            "Deleting the REST API, AWS Lambda function, and security role...")
        time.sleep(5)  # Short sleep avoids TooManyRequestsException.
        wrapper.delete_function(LAMBDA_NAME)
        for pol in iam_role.attached_policies.all():
            pol.detach_role(RoleName=iam_role.name)
        iam_role.delete()
        logging.info(f"Deleted role {iam_role.name}.")
        if apig_client and api_id:
            delete_rest_api(apig_client, api_id)
    logging.info("Thanks for watching!")


if __name__ == '__main__':
    usage_demo()
