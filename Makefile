.PHONY: help install build deploy test clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install development dependencies"
	@echo "  make build      - Build SAM application"
	@echo "  make deploy-dev - Deploy to dev environment"
	@echo "  make deploy-staging - Deploy to staging environment"
	@echo "  make deploy-prod - Deploy to prod environment"
	@echo "  make test       - Run local tests"
	@echo "  make invoke     - Invoke function locally"
	@echo "  make logs       - Tail Lambda logs"
	@echo "  make clean      - Clean build artifacts"

install:
	pip install aws-sam-cli boto3 pytest

build:
	sam build

validate:
	sam validate

deploy-dev:
	sam build && sam deploy --config-env dev

deploy-staging:
	sam build && sam deploy --config-env staging

deploy-prod:
	sam build && sam deploy --config-env prod

test:
	pytest tests/ -v

invoke:
	sam local invoke BedrockAgentFunction -e events/test-event.json

logs:
	sam logs -n BedrockAgentFunction --stack-name bedrock-agentcore-lambda-dev --tail

clean:
	rm -rf .aws-sam
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Quick deployment commands
quick-deploy-dev: build deploy-dev

quick-deploy-prod: build deploy-prod
