import os
from typing import Optional

import jsii
from aws_cdk import(
    core,
    aws_apigatewayv2 as apigw,
    aws_certificatemanager as certmgr,
    aws_cloudformation as cfn,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_route53 as route53,
    aws_route53_targets as route53_targets,
    aws_s3 as s3)

from .utils import make_python_zip_bundle


BASE_PATH = os.path.dirname(os.path.abspath(__file__))
LOG_RETENTION = getattr(logs.RetentionDays, os.getenv('LOG_RETENTION', 'TWO_WEEKS'))


@jsii.implements(route53.IAliasRecordTarget)
class ApiGatewayV2Domain(object):
    def __init__(self, domain_name: apigw.CfnDomainName):
        self.domain_name = domain_name

    @jsii.member(jsii_name='bind')
    def bind(self, _record: route53.IRecordSet) -> route53.AliasRecordTargetConfig:
        return {
            'dnsName': self.domain_name.get_att('RegionalDomainName').to_string(),
            'hostedZoneId': self.domain_name.get_att('RegionalHostedZoneId').to_string()
        }


class CustomDomainStack(cfn.NestedStack):
    def __init__(self, scope: core.Construct, id: str,
        hosted_zone_id: str,
        hosted_zone_name: str,
        domain_name: str,
        api: apigw.HttpApi):
        super().__init__(scope, id)

        hosted_zone = route53.HostedZone.from_hosted_zone_attributes(self, id='dns-hosted-zone',
            hosted_zone_id=hosted_zone_id,
            zone_name=hosted_zone_name)

        certificate = certmgr.DnsValidatedCertificate(self, 'tls-certificate',
            domain_name=domain_name,
            hosted_zone=hosted_zone,
            validation_method=certmgr.ValidationMethod.DNS)

        custom_domain = apigw.CfnDomainName(self, 'custom-domain',
            domain_name=domain_name,
            domain_name_configurations=[
                apigw.CfnDomainName.DomainNameConfigurationProperty(
                    certificate_arn=certificate.certificate_arn)])

        custom_domain.node.add_dependency(api)
        custom_domain.node.add_dependency(certificate)

        api_mapping = apigw.CfnApiMapping(self, 'custom-domain-mapping',
            api_id=api.http_api_id,
            domain_name=domain_name,
            stage='$default')

        api_mapping.node.add_dependency(custom_domain)

        route53.ARecord(self, 'custom-domain-record',
            target=route53.RecordTarget.from_alias(ApiGatewayV2Domain(custom_domain)),
            zone=hosted_zone,
            record_name=domain_name)


class OnceStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str,
            secret_key: str,
            custom_domain: Optional[str] = None,
            hosted_zone_id: Optional[str] = None,
            hosted_zone_name: Optional[str] = None,
            **kwargs) -> None:
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

        api_url = self.api.url
        if custom_domain is not None:
            api_url = f'https://{custom_domain}/'

        core.CfnOutput(self, 'api-url', value=api_url)

        self.get_upload_ticket_function = lambda_.Function(self, 'get-upload-ticket-function',
            function_name='once-get-upload-ticket',
            description='Returns a pre-signed request to share a file',
            runtime=lambda_.Runtime.PYTHON_3_7,
            code=make_python_zip_bundle(os.path.join(BASE_PATH, 'get-upload-ticket')),
            handler='handler.on_event',
            log_retention=LOG_RETENTION,
            environment={
                'APP_URL': api_url,
                'FILES_TABLE_NAME': self.files_table.table_name,
                'FILES_BUCKET': self.files_bucket.bucket_name,
                'SECRET_KEY': secret_key
            })

        self.files_bucket.grant_put(self.get_upload_ticket_function)
        self.files_table.grant_read_write_data(self.get_upload_ticket_function)

        self.download_and_delete_function = lambda_.Function(self, 'download-and-delete-function',
            function_name='once-download-and-delete',
            description='Serves a file from S3 and deletes it as soon as it has been successfully transferred',
            runtime=lambda_.Runtime.PYTHON_3_7,
            code=lambda_.Code.from_asset(os.path.join(BASE_PATH, 'download-and-delete')),
            handler='handler.on_event',
            log_retention=LOG_RETENTION,
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

        self.cleanup_function = lambda_.Function(self, 'delete-served-files-function',
            function_name='once-delete-served-files',
            description='Deletes files from S3 once they have been marked as deleted in DynamoDB',
            runtime=lambda_.Runtime.PYTHON_3_7,
            code=lambda_.Code.from_asset(os.path.join(BASE_PATH, 'delete-served-files')),
            handler='handler.on_event',
            log_retention=LOG_RETENTION,
            environment={
                'FILES_BUCKET': self.files_bucket.bucket_name,
                'FILES_TABLE_NAME': self.files_table.table_name
            })

        self.files_bucket.grant_delete(self.cleanup_function)
        self.files_table.grant_read_write_data(self.cleanup_function)

        events.Rule(self, 'once-delete-served-files-rule',
            schedule=events.Schedule.rate(core.Duration.hours(24)),
            targets=[targets.LambdaFunction(self.cleanup_function)])

        if custom_domain is not None:
            self.custom_domain_stack = CustomDomainStack(self, 'custom-domain',
                api=self.api,
                domain_name=custom_domain,
                hosted_zone_id=hosted_zone_id,
                hosted_zone_name=hosted_zone_name)
