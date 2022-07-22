# Get edits count for wiki page
Lambda function to get latest_update_time page and number_updates for last month

## Create Lambda function
To create a Lambda function with the [console](https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html) 

## API Gateway
To create API [gateway](https://docs.aws.amazon.com/lambda/latest/dg/services-apigateway.html)

## Check Lambda function
run request
```bash
curl -d {'title': 'Washington,_D.C.'} https://<API_GATEWAY_URL>
```
