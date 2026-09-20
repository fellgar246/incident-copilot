PYTHON ?= python3
TERRAFORM_DIR := infra/environments/dev
ifneq (,$(wildcard .venv/bin))
  export PATH := $(CURDIR)/.venv/bin:$(PATH)
endif

.PHONY: help install lint fmt typecheck test terraform-fmt terraform-validate ci

help:
	@echo "Targets:"
	@echo "  install              Install Python (editable packages + dev) and Node workspaces"
	@echo "  lint                 Ruff + ESLint"
	@echo "  fmt                  Ruff format + terraform fmt"
	@echo "  typecheck            mypy + tsc"
	@echo "  test                 pytest"
	@echo "  terraform-fmt        terraform fmt -recursive"
	@echo "  terraform-validate   terraform init -backend=false && validate"
	@echo "  ci                   lint, typecheck, test, terraform-validate"

install:
	$(PYTHON) -m pip install -e packages/cost-guardrails -e packages/contracts -e packages/observability -e services/simulator -e ".[dev]"
	npm install

lint:
	ruff check .
	npm run lint

fmt:
	ruff format .
	terraform fmt -recursive infra

typecheck:
	mypy packages apps/api services
	npm run typecheck

test:
	pytest

terraform-fmt:
	terraform fmt -recursive infra

terraform-validate:
	cd $(TERRAFORM_DIR) && terraform init -backend=false -input=false
	cd $(TERRAFORM_DIR) && terraform fmt -check
	cd $(TERRAFORM_DIR) && terraform validate

ci: lint typecheck test terraform-validate
