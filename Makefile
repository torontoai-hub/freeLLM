.PHONY: fmt lint test run

fmt:
black app tests
ruff check --fix app tests

lint:
ruff check app tests

test:
pytest

run:
uvicorn app.main:app --host 0.0.0.0 --port 8080
