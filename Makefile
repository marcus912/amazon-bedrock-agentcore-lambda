.PHONY: help install build deploy test clean setup-env

help:
	@echo "Available commands:"
	@echo "  make setup-env  - Create .env from .env.example"
	@echo "  make install    - Install development dependencies"
	@echo "  make build      - Build SAM application"
	@echo "  make deploy-dev - Deploy to dev environment"
	@echo "  make deploy-staging - Deploy to staging environment"
	@echo "  make deploy-prod - Deploy to prod environment"
	@echo "  make test       - Run local tests"
	@echo "  make invoke     - Invoke function locally"
	@echo "  make logs       - Tail Lambda logs"
	@echo "  make clean      - Clean build artifacts"

setup-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file. Please update with your values."; \
	else \
		echo ".env file already exists."; \
	fi

install:
	pip install -r requirements-dev.txt

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
	@if [ -f .env ]; then \
		sam local invoke BedrockAgentFunction -e events/test-event.json --env-vars .env; \
	else \
		echo "Warning: .env file not found. Run 'make setup-env' first."; \
		sam local invoke BedrockAgentFunction -e events/test-event.json; \
	fi

logs:
	sam logs -n BedrockAgentFunction --stack-name bedrock-agentcore-lambda-dev --tail

clean:
	rm -rf .aws-sam
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Quick deployment commands
quick-deploy-dev: build deploy-dev

quick-deploy-prod: build deploy-prod
