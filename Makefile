.PHONY: install cli api mcp ui test lint typecheck

install:
	uv sync --all-extras

cli:
	finsight research AAPL

api:
	finsight-api

mcp:
	finsight-mcp

ui:
	streamlit run src/finsight/ui.py

test:
	pytest -q

lint:
	ruff check .

typecheck:
	mypy
