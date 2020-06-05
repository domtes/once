# once: a one-time file sharing personal service

It happens that I want to share a file with someone which is sensitive enough
that I don't want to upload on a public free service.
 
I would like to have something like transfer.sh, running
 as a personal service, with the following features:

- it must be serverless (I'm not willing to pay except for the actual file storage, and only for the time strictly required)
- it must return a link that I can share to anyone
- file must be deleted as soon as it get *successfully downloaded*
- it must expose a simple HTTP API, so *curl* should suffice to share a file
- it must be protected with some form of authentication

With CDK I could create the following resources:

- An S3 bucket to host the uploaded files
- A Lambda function to implement the 'get-upload-ticket'
- A Dynamodb table to store the information about the entries
- Another Lambda function to implement a "smart" download handler, to delete the file after the very first successful transfer.

I will use API Gateway to expose the lambda functions as an HTTP API.


HERE BE DIAGRAM!


    mkdir once
    cd once
    cdk init app

Then it should be easy to start organizing the project layout.
One single stack, one folder for each lambda function.
