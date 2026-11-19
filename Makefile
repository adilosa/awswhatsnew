SAM := uvx --from aws-sam-cli sam
# sam build needs a python matching the lambda runtime (with pip) on the PATH
BUILD_VENV := .build-venv

uv.lock: pyproject.toml
	uv lock

requirements.txt: uv.lock
	uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt

$(BUILD_VENV):
	uv venv --seed --python 3.12 $(BUILD_VENV)

build: template.yml requirements.txt src/*.py | $(BUILD_VENV)
	uv run cfn-lint template.yml
	PATH="$(CURDIR)/$(BUILD_VENV)/bin:$$PATH" $(SAM) build -m requirements.txt

packaged.yml: build
	$(SAM) package --s3-bucket awswhatsnew-artifacts --output-template-file packaged.yml

deploy: packaged.yml
	$(SAM) deploy --template-file packaged.yml --capabilities CAPABILITY_IAM --stack-name awswhatsnew --region us-west-2

clean:
	rm -rf .aws-sam packaged.yml

.PHONY: build deploy clean
