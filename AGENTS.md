# AGENTS.md

## Project Purpose

This repository is a governed ecommerce analytics MVP for the Maven Fuzzy Factory CSV dataset. It answers natural-language business questions through deterministic metric definitions, parameterized SQL templates, programmatic validation, audit logging, and an eval harness.

This is not a general CSV chatbot. Do not add generic file-question-answering behavior, free-form SQL generation, or prompt-only metric logic.

## Dataset Tables and Grain

- `maven_fuzzy_factory_data_dictionary.csv`: table and field reference guide.
- `website_sessions.csv`: one row per website session.
- `website_pageviews.csv`: one row per pageview.
- `orders.csv`: one row per completed order.
- `order_items.csv`: one row per purchased item.
- `order_item_refunds.csv`: one row per refunded order item.
- `products.csv`: one row per product.

Critical grain rules:

- Never count pageviews as sessions.
- Never multiply revenue by joining pageviews directly to orders without explicit grain control.
- Use `website_sessions` as the denominator source for conversion-rate metrics.
- Use `orders` for order-level revenue and conversion outcomes.
- Use `order_items` for product-level revenue and margin.
- Use `order_item_refunds` for refund metrics, joined through `order_item_id`.
- Treat refund-date attribution and order-date attribution as separate business policies.

## Join Rules

Approved core joins:

- `website_sessions.website_session_id = website_pageviews.website_session_id`
- `website_sessions.website_session_id = orders.website_session_id`
- `orders.order_id = order_items.order_id`
- `order_items.order_item_id = order_item_refunds.order_item_id`
- `products.product_id = orders.primary_product_id`
- `products.product_id = order_items.product_id`

Conversion-rate calculations must use `LEFT JOIN` from `website_sessions` to `orders` so non-converting sessions remain in the denominator.

When joining pageviews to orders or order items, aggregate pageviews to session-level or otherwise control grain before joining to revenue-bearing tables.

## Metric Governance

- Metric definitions must live in versioned configuration or code under `src/semantic_layer`, not in prompts.
- SQL must be produced from named, parameterized templates under `src/templates/sql_templates`.
- Runtime answers must eventually include the metric definition, assumptions, validation status, SQL used, and audit trace ID.
- Do not invent metric definitions in prompts or one-off runtime text.
- Do not implement free-form SQL execution in the MVP.
- Prefer deterministic code and configuration over LLM reasoning.

## Runtime Architecture

The intended runtime path is:

1. Question classifier / ambiguity detector
2. Template matcher
3. Metric and template contract loader
4. SQL renderer
5. DuckDB executor
6. Programmatic validator
7. Answer explainer
8. Audit logger

Do not add LangGraph yet. Optional Langfuse or LangSmith tracing can be added later through `src/observability`.

## Validation-First Development

- Add validation rules before broadening query coverage.
- Validate row grain, denominator source, join policy, date attribution policy, and required output columns.
- Prefer tests that catch metric drift and accidental fanout joins.
- Add eval cases to `src/evals` as supported questions become available.

## Test Expectations

- Run `python -m pytest` before considering work done.
- Add or update tests for new semantic metrics, templates, validators, and runtime branches.
- Keep placeholder tests minimal, but replace them with behavior tests as the scaffold matures.

## Coding Standards

- Use Python, DuckDB, Pandas, PyYAML, pytest, and pathlib.
- Do not hardcode absolute local paths.
- Use `pathlib.Path` for filesystem paths.
- Keep modules small and explicit.
- Prefer typed function signatures where useful.
- Keep configuration human-readable and version-controlled.
- Avoid unnecessary dependencies.

## Data and Git Rules

- Do not commit raw CSV files.
- Do not commit local DuckDB database files, SQLite database files, exports, cache files, audit logs, or `.env` files.
- Keep `data/raw/.gitkeep` and `data/processed/.gitkeep` tracked so local data folders exist without storing data in Git.
- Local CSV files should be placed in `data/raw/` and remain ignored by Git.

## Run Commands

Initial setup:

```bash
python -m venv .venv
python -m pip install -e .
```

Future local app command, after the Streamlit UI exists:

```bash
python -m streamlit run app/main.py
```

## Test Commands

```bash
python -m pytest
```

## Definition of Done

Work is done when:

- New runtime behavior is backed by deterministic metric definitions and SQL templates.
- Query outputs include assumptions, validation status, SQL used, and an audit trace ID when the runtime supports answers.
- Tests cover the changed metric, template, validator, or runtime path.
- Raw CSVs and local database files are not staged.
- `python -m pytest` passes.
- Documentation is updated when architecture, metric policy, data placement, or run commands change.


# Audit remediation metadata
audit_path: audit/multi_repo/2026-09-18/repo_mavenfuzzyfactory_20260918T004904Z.json
risk_level: MEDIUM
human_review_required: false
audit_findings:
  - "Risk level is MEDIUM, expected LOW."
  - "Dependency manifests present: pyproject.toml"
  - "CI/CD workflow configuration present (.github/workflows)."
  - "HTTP networking libraries in use: requests"
  - "Test suite present — actively developed project."

