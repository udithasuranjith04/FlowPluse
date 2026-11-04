PYTHON := .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.12
.PHONY: release-preflight verify-people setup dev demo test lint build benchmark benchmark-model evaluate-counts fixture model e2e verify-model verify-digitraffic verify-positive verify-tms cameras verify-live verify-road
setup:
	$(PYTHON_BOOTSTRAP) -m venv .venv
	$(PYTHON) -m pip install -e './backend[dev]'
	cd frontend && npm ci

dev:
	ROADPULSE_AUTOSTART=false $(PYTHON) scripts/dev.py

demo:
	ROADPULSE_AUTOSTART=true ROADPULSE_CAMERA_MODE=replay ROADPULSE_CAMERA_URL= ROADPULSE_REPLAY_PATH= $(PYTHON) scripts/dev.py

test:
	$(PYTHON) -m pytest -q backend/tests
	cd frontend && npm test

lint:
	$(PYTHON) -m ruff check backend scripts
	$(PYTHON) -m ruff format --check backend scripts
	$(PYTHON) -m mypy --config-file backend/pyproject.toml backend/app
	cd frontend && npm run lint && npm run typecheck

build:
	cd frontend && npm run build

benchmark:
	$(PYTHON) backend/scripts/benchmark.py

benchmark-model:
	$(PYTHON) backend/scripts/benchmark_model.py

fixture:
	$(PYTHON) backend/scripts/make_synthetic_fixture.py

model:
	$(PYTHON) -m pip install -e './backend[vision]'
	$(PYTHON) backend/scripts/download_model.py

e2e:
	cd frontend && npm run test:e2e

verify-model:
	$(PYTHON) backend/scripts/verify_model.py

verify-digitraffic:
	$(PYTHON) backend/scripts/verify_digitraffic.py

verify-positive:
	$(PYTHON) backend/scripts/verify_digitraffic.py --seek-positive

verify-tms:
	$(PYTHON) backend/scripts/verify_tms.py

cameras:
	$(PYTHON) backend/scripts/list_cameras.py

verify-live:
	$(PYTHON) backend/scripts/verify_live.py

verify-road:
	$(PYTHON) backend/scripts/verify_live.py --require-vehicles --seconds 30

verify-people:
	$(PYTHON) backend/scripts/verify_people.py --seconds 15

# Example: make evaluate-counts FILE=/absolute/path/to/counts.csv
evaluate-counts:
	@test -n "$(FILE)" || (echo "Specify FILE=/path/to/counts.csv" && exit 2)
	$(PYTHON) backend/scripts/evaluate_counts.py "$(FILE)"

release-preflight:
	python3 scripts/release_prep.py
