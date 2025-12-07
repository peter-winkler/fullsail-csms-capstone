.PHONY: help install dev-up dev-down test lint format clean k8s-apply tf-plan tf-apply dashboard dashboard-docker

# Default target
help:
	@echo "KinaTrax Cloud Pipeline - Development Commands"
	@echo ""
	@echo "Setup & Dependencies:"
	@echo "  make install       Install all project dependencies using uv"
	@echo "  make install-dev   Install development dependencies"
	@echo ""
	@echo "Dashboard:"
	@echo "  make dashboard     Run dashboard locally (streamlit)"
	@echo "  make dashboard-docker  Run dashboard in Docker"
	@echo ""
	@echo "Local Development:"
	@echo "  make dev-up        Start local development environment (docker-compose)"
	@echo "  make dev-down      Stop local development environment"
	@echo "  make dev-logs      View logs from all services"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format        Format code with black and isort"
	@echo "  make lint          Run linters (flake8, mypy)"
	@echo "  make test          Run all tests with coverage"
	@echo "  make test-unit     Run unit tests only"
	@echo "  make test-int      Run integration tests only"
	@echo ""
	@echo "Kubernetes:"
	@echo "  make k8s-apply-dev Deploy to local Kubernetes (dev overlay)"
	@echo "  make k8s-delete    Delete Kubernetes resources"
	@echo ""
	@echo "Terraform:"
	@echo "  make tf-init       Initialize Terraform"
	@echo "  make tf-plan       Plan infrastructure changes"
	@echo "  make tf-apply      Apply infrastructure changes"
	@echo "  make tf-destroy    Destroy infrastructure"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove build artifacts and cache files"

# Install dependencies
install:
	uv sync

install-dev:
	uv sync --all-extras

# Local development environment
dev-up:
	docker-compose up -d
	@echo "Development environment started!"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - Redis: localhost:6379"
	@echo "  - Kafka: localhost:29092"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000 (admin/admin)"

dev-down:
	docker-compose down

dev-logs:
	docker-compose logs -f

# Code formatting
format:
	black src/ tests/
	isort src/ tests/

# Linting
lint:
	flake8 src/ tests/
	mypy src/

# Testing
test:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-int:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

# Kubernetes deployment
k8s-apply-dev:
	kubectl apply -k infrastructure/kubernetes/overlays/dev

k8s-delete:
	kubectl delete -k infrastructure/kubernetes/overlays/dev

# Terraform infrastructure
tf-init:
	cd infrastructure/terraform/environments/dev && terraform init

tf-plan:
	cd infrastructure/terraform/environments/dev && terraform plan

tf-apply:
	cd infrastructure/terraform/environments/dev && terraform apply

tf-destroy:
	cd infrastructure/terraform/environments/dev && terraform destroy

# Dashboard
dashboard:
	cd src/dashboard && uv run streamlit run app/main.py

dashboard-docker:
	docker-compose up dashboard --build
	@echo "Dashboard available at: http://localhost:8501"

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	@echo "Cleaned build artifacts and cache files"
