PYTHON ?= python3
TERRAFORM_DIR := infra/environments/dev
ifneq (,$(wildcard $(CURDIR)/.venv/bin/python))
  PYTHON := $(CURDIR)/.venv/bin/python
endif

.PHONY: help install lint fmt typecheck test terraform-fmt terraform-validate ci eval eval-full run-api openapi

help:
	@echo "Targets:"
	@echo "  install              Install Python (editable packages + dev) and Node workspaces"
	@echo "  lint                 Ruff + ESLint"
	@echo "  fmt                  Ruff format + terraform fmt"
	@echo "  typecheck            mypy + tsc"
	@echo "  test                 pytest"
	@echo "  terraform-fmt        terraform fmt -recursive"
	@echo "  terraform-validate   terraform fmt -check + init -backend=false + validate"
	@echo "  run-api              Run the FastAPI app locally (in-memory repository)"
	@echo "  openapi              Write apps/api/openapi.json from the live application"
	@echo "  eval                 Offline PR evaluation subset and quality gates"
	@echo "  eval-full            Offline evaluation suite"
	@echo "  ci                   lint, typecheck, test, eval, terraform-validate"

install:
	$(PYTHON) -m pip install -e packages/cost-guardrails -e packages/contracts -e packages/observability -e packages/evaluations -e services/simulator -e services/incident-worker -e services/tools/cloudwatch -e services/tools/deployments -e services/tools/knowledge -e services/tools/remediation -e services/agent -e apps/api -e ".[dev]"
	npm install

lint:
	$(PYTHON) -m ruff check .
	npm run lint

fmt:
	$(PYTHON) -m ruff format .
	terraform fmt -recursive infra

typecheck:
	$(PYTHON) -m mypy packages apps/api services
	npm run typecheck

test:
	$(PYTHON) -m pytest

eval:
	$(PYTHON) scripts/run_evaluations.py --profile pr

eval-full:
	$(PYTHON) scripts/run_evaluations.py --profile full

terraform-fmt:
	terraform fmt -recursive infra

terraform-validate:
	terraform fmt -check -recursive infra
	cd $(TERRAFORM_DIR) && terraform init -backend=false -input=false
	cd $(TERRAFORM_DIR) && terraform validate

ci: lint typecheck test eval terraform-validate

run-api:
	$(PYTHON) -m uvicorn api.main:app --reload --app-dir apps/api/src

openapi:
	$(PYTHON) -c "from pathlib import Path; import json; from api.main import create_app; Path('apps/api/openapi.json').write_text(json.dumps(create_app().openapi(), indent=2) + chr(10), encoding='utf-8')"
