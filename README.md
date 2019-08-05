# awswhatsnew

Publish AWS News to Twitter by reading the official RSS feed with AWS Lambda.

## Details

- Dependencies managed via [Pipenv](https://github.com/kennethreitz/pipenv)
- Infrastructure defined in CloudFormation in [`template.yml`](template.yml)
- Local testing via Docker and [SAM Local](http://docs.aws.amazon.com/lambda/latest/dg/test-sam-local.html#sam-cli-simple-app)
- Packaging and Deployment done via [`Makefile`](Makefile) and SAM CLI, using `sam build`, `sam package`, and `sam deploy`
