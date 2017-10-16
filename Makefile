lambda.zip: dependencies.zip *.py
	cp dependencies.zip lambda.zip
	zip -g lambda.zip *.py

dependencies.zip: Pipfile
	cd `pipenv --venv`/lib/python3.6/site-packages; zip -r9 lambda.zip *
	mv `pipenv --venv`/lib/python3.6/site-packages/lambda.zip dependencies.zip

packaged.yml: template.yml lambda.zip
	cfn-lint validate template.yml
	sam package --template-file template.yml --s3-bucket awswhatsnew-artifacts --output-template-file packaged.yml

deploy: packaged.yml lambda.zip
	sam deploy --template-file packaged.yml --capabilities CAPABILITY_IAM --stack-name awswhatsnew


clean:
	rm dependencies.zip lambda.zip packaged.yml
