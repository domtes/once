import os

from aws_cdk import(
    core,
    aws_apigatewayv2 as apigw,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_s3 as s3)

from .utils import make_python_zip_bundle


BASE_PATH = os.path.dirname(os.path.abspath(__file__))


class OnceStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.files_bucket = s3.Bucket(self, 'files-bucket',
            bucket_name='once-shared-files',
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=core.RemovalPolicy.DESTROY)

        self.files_table = dynamodb.Table(self, 'once-files-table',
            table_name='once-files',
            partition_key=dynamodb.Attribute(name='id', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=core.RemovalPolicy.DESTROY)

        self.api = apigw.HttpApi(self, 'once-api', api_name='once-api')

        self.get_upload_ticket_function = lambda_.Function(self, 'get-upload-ticket-function',
            function_name='once-get-upload-ticket',
            runtime=lambda_.Runtime.PYTHON_3_7,
            code=make_python_zip_bundle(os.path.join(BASE_PATH, 'get-upload-ticket')),
            handler='handler.on_event',
            description='Returns a pre-signed request to share a file',
            environment={
                'APP_URL': self.api.url,
                'FILES_TABLE_NAME': self.files_table.table_name,
                'FILES_BUCKET': self.files_bucket.bucket_name
            })

        self.files_bucket.grant_put(self.get_upload_ticket_function)
        self.files_table.grant_read_write_data(self.get_upload_ticket_function)

        self.download_and_delete_function = lambda_.Function(self, 'download-and-delete-function',
            function_name='once-download-and-delete',
            runtime=lambda_.Runtime.PYTHON_3_7,
            code=lambda_.Code.from_asset(os.path.join(BASE_PATH, 'download-and-delete')),
            handler='handler.on_event',
            description='Serves a file from S3 and deletes it as soon as it has been successfully transferred.',
            environment={
                'FILES_BUCKET': self.files_bucket.bucket_name,
                'FILES_TABLE_NAME': self.files_table.table_name
            })

        self.files_bucket.grant_read(self.download_and_delete_function)
        self.files_bucket.grant_delete(self.download_and_delete_function)
        self.files_table.grant_read_write_data(self.download_and_delete_function)

        get_upload_ticket_integration = apigw.LambdaProxyIntegration(handler=self.get_upload_ticket_function)
        self.api.add_routes(
            path='/',
            methods=[apigw.HttpMethod.GET],
            integration=get_upload_ticket_integration)

        download_and_delete_integration = apigw.LambdaProxyIntegration(handler=self.download_and_delete_function)
        self.api.add_routes(
            path='/{entry_id}/{filename}',
            methods=[apigw.HttpMethod.GET],
            integration=download_and_delete_integration)

        core.CfnOutput(self, 'api-url', value=self.api.url)
