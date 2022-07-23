# Demo script to create AWS lambda and API gateway
Based on official examples from [AWS](https://docs.aws.amazon.com/code-samples/latest/catalog/code-catalog-python-example_code-lambda.html)

## Configuration
    AWS_ACCESS_KEY - aws_access_key_id
    AWS_SECRET_KEY - aws_secret_access_key
    API_BASE_PATH - API base path name, for example 'demoapi'
    API_STAGE - API gateway stage name, for example 'test'
    LAMBDA_NAME - lambda function name, for example 'lambda_example'
    LAMBDA_FILENAME - lambda function file name, for example 'lambda_example/index.py'
    LAMBDA_HANDLER_NAME - lambda handler name, for example 'index.lambda_handler'
    API_NAME - API name, for example f'{LAMBDA_NAME}-rest-api'
    TEST_PARAMS - parameters for lambda test, for example {'title': 'Washington,_D.C.'}
    IS_REMOVE - Do we need to delete all lambda functions, roles and api gateway. True by default
    IS_API_CREATE - Do we need to create an api gateway. True by default
    IS_REQUIREMENTS - Do we need to install addition python libs. True by default

## Pre process
According AWS lambda documentation, to install requirement python libs, you need to create a package with all required libs.
There is a bash script for this process. Run script
```bash
/bin/bash ./setup.sh
```
This script will create a "package" directory inside the lambda_example directory, install
all required libs in lambda_example/package dir, will create zip package with libs and add lambda file to zip
## Usage
Run script to create lambda and api gateway
```bash
python lambda_with_api_demo.py
```

Note: if you have changed your lambda and want to upload a new one with script, 
you need recreate zip package with setup.sh
