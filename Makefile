# Reproduction pipeline. Run `make data` once (requires a GENESIS token), then `make all`.
.PHONY: setup test lint data inputs validate models backtest sensitivities posthoc audit \
        procedures regional extended tables figures analysis all clean

PY := uv run python
ICD := ICD10C=ICD10-C70,ICD10-C71,ICD10-C72,ICD10-D32,ICD10-D33,ICD10-G91,ICD10-I60,ICD10-I61,ICD10-I62,ICD10-S06
OPS := OPS4=OPS-5-013,OPS-5-015,OPS-5-022,OPS-5-023
VAR1 := BEVPR1=BEV-VARIANTE-01,BEV-VARIANTE-02,BEV-VARIANTE-03
VAR2 := BEVPR2=BEV-VARIANTE-01,BEV-VARIANTE-02,BEV-VARIANTE-03
SEX := GES=GESM,GESW
GET := $(PY) scripts/acquire_genesis.py
ENV := set -a; [ -f .env ] && . ./.env; set +a;

setup:
	uv sync --locked

test:
	uv run pytest

lint:
	uv run ruff check .

# Official source tables (GENESIS-Online). Requires DESTATIS_GENESIS_TOKEN in .env or the environment.
data:
	$(ENV) $(GET) --table 23131-0002 --start-year 2005 --end-year 2024 --no-compress --classifying-selection '$(ICD)'
	$(ENV) $(GET) --table 12411-0006 --start-year 2005 --end-year 2024 --classifying-selection '$(SEX)'
	$(ENV) $(GET) --table 12421-0002 --start-year 2030 --end-year 2040 --classifying-selection '$(VAR1)' --classifying-selection '$(SEX)'
	$(ENV) $(GET) --table 23141-0102 --start-year 2019 --end-year 2024 --no-compress --classifying-selection '$(OPS)'
	$(ENV) $(GET) --table 23131-0011 --start-year 2022 --end-year 2024 --no-compress --classifying-selection '$(ICD)'
	$(ENV) $(GET) --table 12411-0013 --start-year 2022 --end-year 2024
	$(ENV) for y in 2030 2035 2040; do $(GET) --table 12421-0004 --start-year $$y --end-year $$y --classifying-selection '$(VAR2)'; done
	$(ENV) $(GET) --table 23131-0012 --start-year 2024 --end-year 2024
	$(ENV) for y in 2030 2034 2035 2040; do $(GET) --table 12421-0002 --start-year $$y --end-year $$y --classifying-selection '$(SEX)' --output-dir data/raw/genesis_sensitivity; done
	$(ENV) $(GET) --table 12411-0041 --start-year 2024 --end-year 2024 --output-dir data/raw/genesis_sensitivity

inputs:
	$(PY) scripts/prepare_inputs.py

validate:
	$(PY) scripts/validate_inputs.py

models: validate
	$(PY) scripts/run_models_01.py

backtest: validate
	$(PY) scripts/run_backtest.py

sensitivities: validate
	$(PY) scripts/run_sensitivities.py

posthoc: models backtest sensitivities
	$(PY) scripts/run_posthoc.py

audit:
	$(PY) scripts/run_icd_audit.py

procedures: validate
	$(PY) scripts/run_ops.py

regional: models
	$(PY) scripts/run_regional.py
	$(PY) scripts/make_regional_outputs.py

extended: regional backtest
	$(PY) scripts/run_extended_sensitivity.py

tables: posthoc audit procedures extended
	$(PY) scripts/make_tables.py
	$(PY) scripts/make_manuscript_tables_md.py

figures: tables
	$(PY) scripts/make_manuscript_figures.py

analysis: figures

all: lint test inputs analysis

clean:
	rm -rf data/processed/*.csv data/interim/* outputs/tables/*.csv outputs/logs/*.json \
	       outputs/figures/* outputs/manuscript_tables
