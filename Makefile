Pipfile.lock: Pipfile
	pipenv lock 

requirements.txt: Pipfile.lock
	pipenv lock -r > requirements.txt

packaged.yml: template.yml requirements.txt *.py
	pipenv run cfn-lint template.yml
	pipenv run sam build -m requirements.txt 
	pipenv run sam package --s3-bucket awswhatsnew-artifacts --output-template-file packaged.yml

deploy: packaged.yml
	sam deploy --template-file packaged.yml --capabilities CAPABILITY_IAM --stack-name awswhatsnew --region us-west-2


clean:
	rm dependencies.zip lambda.zip packaged.yml
