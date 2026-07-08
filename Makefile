PYTHON := .venv/bin/python
VENV_BIN := .venv/bin
SRC_DIR := src/psas_psarc

.PHONY: lint format

lint:
	@echo "Running codespell..."
	@$(VENV_BIN)/codespell $(SRC_DIR) --toml pyproject.toml
	@echo "Running ruff..."
	@$(VENV_BIN)/ruff check $(SRC_DIR)
	@echo "Running vulture..."
	@$(VENV_BIN)/vulture --min-confidence 100 $(SRC_DIR)
	@echo "Running isort..."
	@$(VENV_BIN)/isort --check-only --profile black $(SRC_DIR)
	@echo "Running black..."
	@$(VENV_BIN)/black --check $(SRC_DIR)
	@echo "Running validate-pyproject..."
	@$(VENV_BIN)/validate-pyproject pyproject.toml

format:
	@echo "Formatting imports..."
	@$(VENV_BIN)/isort --profile black $(SRC_DIR)
	@echo "Formatting code..."
	@$(VENV_BIN)/black $(SRC_DIR)
