# Makefile for Houkokusou Chatbot

# Variables
PYTHON := python3
PIP := pip3
CDK := npx cdk
NPM := npm
IONIC := npx ionic

# Environment
ENV ?= dev

# Directories
LAMBDA_DIR := src/lambda
FRONTEND_DIR := src/frontend
INFRA_DIR := infrastructure

# Colors
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: setup
setup: ## Setup development environment
	@echo "$(GREEN)Setting up development environment...$(NC)"
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && sam local start-api --template cdk.out/*-template.json

.PHONY: watch
watch: ## Watch for changes and rebuild
	@echo "$(GREEN)Watching for changes...$(NC)"
	. .venv/bin/activate && $(CDK) watch --context env=$(ENV)

.PHONY: bootstrap
bootstrap: ## Bootstrap CDK
	@echo "$(GREEN)Bootstrapping CDK...$(NC)"
	. .venv/bin/activate && $(CDK) bootstrap --context env=$(ENV)

.PHONY: clean
clean: ## Clean build artifacts
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf cdk.out
	rm -rf $(FRONTEND_DIR)/www
	@echo "$(GREEN)Clean complete!$(NC)"

.PHONY: validate
validate: lint test ## Validate code (lint + test)
	@echo "$(GREEN)Validation complete!$(NC)"

.PHONY: security-scan
security-scan: ## Run security scan
	@echo "$(GREEN)Running security scan...$(NC)"
	. .venv/bin/activate && bandit -r $(LAMBDA_DIR) $(INFRA_DIR)
	. .venv/bin/activate && safety check
	cd $(FRONTEND_DIR) && $(NPM) audit

.PHONY: update-deps
update-deps: ## Update dependencies
	@echo "$(GREEN)Updating dependencies...$(NC)"
	. .venv/bin/activate && pip-compile --upgrade requirements.in
	cd $(FRONTEND_DIR) && $(NPM) update

.PHONY: docker-build
docker-build: ## Build Docker images for Lambda
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker build -t houkokusou-lambda-base -f docker/lambda/Dockerfile .

.PHONY: monitoring-setup
monitoring-setup: ## Setup CloudWatch dashboards
	@echo "$(GREEN)Setting up monitoring...$(NC)"
	. .venv/bin/activate && python scripts/setup/setup-monitoring.py --env $(ENV)

# Development shortcuts
.PHONY: dev
dev: ## Start development environment
	@echo "$(GREEN)Starting development environment...$(NC)"
	tmux new-session -d -s houkokusou-dev
	tmux send-keys -t houkokusou-dev:0 "make local-frontend" C-m
	tmux split-window -t houkokusou-dev:0 -h
	tmux send-keys -t houkokusou-dev:0 "make watch" C-m
	tmux attach -t houkokusou-dev

.PHONY: prod-deploy
prod-deploy: ## Deploy to production with confirmation
	@echo "$(RED)WARNING: Deploying to PRODUCTION$(NC)"
	@echo "Current branch: $(git branch --show-current)"
	@echo "Last commit: $(git log -1 --oneline)"
	@read -p "Deploy to production? (yes/no) " confirm && \
	if [ "$confirm" = "yes" ]; then \
		$(MAKE) validate && \
		$(MAKE) deploy ENV=prod; \
	fi

# Default target
.DEFAULT_GOAL := helpbin/activate && $(PIP) install -r requirements.txt
	. .venv/bin/activate && $(PIP) install -r requirements-dev.txt
	cd $(FRONTEND_DIR) && $(NPM) install
	@echo "$(GREEN)Setup complete!$(NC)"

.PHONY: install-deps
install-deps: ## Install all dependencies
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	. .venv/bin/activate && $(PIP) install -r requirements.txt
	@echo "$(GREEN)Installing Lambda dependencies...$(NC)"
	$(MAKE) install-lambda-deps
	@echo "$(GREEN)Installing frontend dependencies...$(NC)"
	cd $(FRONTEND_DIR) && $(NPM) install

.PHONY: install-lambda-deps
install-lambda-deps: ## Install Lambda function dependencies
	@echo "$(GREEN)Installing Lambda dependencies...$(NC)"
	@for dir in $(LAMBDA_DIR)/api/* $(LAMBDA_DIR)/processors/* $(LAMBDA_DIR)/admin/*; do \
		if [ -f $$dir/requirements.txt ]; then \
			echo "Installing dependencies for $$dir"; \
			$(PIP) install -r $$dir/requirements.txt -t $$dir/; \
		fi \
	done
	@echo "$(GREEN)Building Lambda layers...$(NC)"
	./scripts/utils/build-lambda-layers.sh

.PHONY: build
build: ## Build all components
	@echo "$(GREEN)Building application...$(NC)"
	$(MAKE) build-lambda
	$(MAKE) build-frontend

.PHONY: build-lambda
build-lambda: ## Build Lambda functions
	@echo "$(GREEN)Building Lambda functions...$(NC)"
	./scripts/utils/build-lambda-layers.sh
	@echo "$(GREEN)Lambda build complete!$(NC)"

.PHONY: build-frontend
build-frontend: ## Build frontend
	@echo "$(GREEN)Building frontend...$(NC)"
	cd $(FRONTEND_DIR) && $(IONIC) build --prod
	@echo "$(GREEN)Frontend build complete!$(NC)"

.PHONY: test
test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	$(MAKE) test-unit
	$(MAKE) test-integration

.PHONY: test-unit
test-unit: ## Run unit tests
	@echo "$(GREEN)Running unit tests...$(NC)"
	. .venv/bin/activate && pytest tests/unit -v --cov=src --cov-report=html

.PHONY: test-integration
test-integration: ## Run integration tests
	@echo "$(GREEN)Running integration tests...$(NC)"
	. .venv/bin/activate && pytest tests/integration -v

.PHONY: lint
lint: ## Run linters
	@echo "$(GREEN)Running linters...$(NC)"
	. .venv/bin/activate && flake8 $(LAMBDA_DIR) $(INFRA_DIR)
	. .venv/bin/activate && black --check $(LAMBDA_DIR) $(INFRA_DIR)
	. .venv/bin/activate && mypy $(LAMBDA_DIR) $(INFRA_DIR)
	cd $(FRONTEND_DIR) && $(NPM) run lint

.PHONY: format
format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	. .venv/bin/activate && black $(LAMBDA_DIR) $(INFRA_DIR)
	cd $(FRONTEND_DIR) && $(NPM) run format

.PHONY: synth
synth: ## Synthesize CDK app
	@echo "$(GREEN)Synthesizing CDK app...$(NC)"
	. .venv/bin/activate && $(CDK) synth --context env=$(ENV)

.PHONY: diff
diff: ## Show CDK diff
	@echo "$(GREEN)Showing CDK diff...$(NC)"
	. .venv/bin/activate && $(CDK) diff --context env=$(ENV)

.PHONY: deploy
deploy: build ## Deploy to AWS
	@echo "$(GREEN)Deploying to $(ENV) environment...$(NC)"
	./scripts/deploy/deploy.sh $(ENV)

.PHONY: deploy-backend
deploy-backend: build-lambda ## Deploy backend only
	@echo "$(GREEN)Deploying backend to $(ENV) environment...$(NC)"
	. .venv/bin/activate && $(CDK) deploy --context env=$(ENV) --require-approval never

.PHONY: deploy-frontend
deploy-frontend: build-frontend ## Deploy frontend only
	@echo "$(GREEN)Deploying frontend...$(NC)"
	./scripts/utils/sync-frontend.sh $(ENV)

.PHONY: destroy
destroy: ## Destroy CDK stack
	@echo "$(RED)Destroying $(ENV) environment...$(NC)"
	@read -p "Are you sure? (y/N) " confirm && \
	if [ "$$confirm" = "y" ]; then \
		. .venv/bin/activate && $(CDK) destroy --context env=$(ENV) --force; \
	fi

.PHONY: logs
logs: ## Show CloudWatch logs
	@echo "$(GREEN)Showing CloudWatch logs...$(NC)"
	. .venv/bin/activate && $(CDK) logs --context env=$(ENV)

.PHONY: seed-data
seed-data: ## Seed initial data
	@echo "$(GREEN)Seeding initial data...$(NC)"
	. .venv/bin/activate && python scripts/setup/seed-data.py --env $(ENV)

.PHONY: local-frontend
local-frontend: ## Run frontend locally
	@echo "$(GREEN)Starting frontend locally...$(NC)"
	cd $(FRONTEND_DIR) && $(IONIC) serve

.PHONY: local-api
local-api: ## Run API locally (using SAM)
	@echo "$(GREEN)Starting API locally...$(NC)"
	. .venv/