.PHONY: test eval lint format run

test:
	pytest

eval:
	python scripts/run_eval.py

lint:
	ruff check .

format:
	black .

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000
