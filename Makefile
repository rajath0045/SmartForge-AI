.PHONY: install seed api web test build verify

install:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

seed:
	cd backend && .venv/bin/python -m app.seed

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/pytest -q

build:
	cd frontend && npm run build

verify: test build

