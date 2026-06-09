# Governed Ecommerce Analytics MVP

This project is the initial scaffold for a governed analytics application using the Maven Fuzzy Factory ecommerce and web analytics CSV dataset. The goal is to answer natural-language business questions through deterministic metric definitions, parameterized SQL templates, programmatic validation, audit logging, and an eval harness.

This is not a general CSV chatbot. The MVP should only answer supported business questions through governed metrics and approved templates.

## For A Novice Reader

This app is a business analytics dashboard for an ecommerce dataset. Instead of
letting the computer invent any SQL it wants, it answers a short list of approved
questions, such as conversion by channel, conversion by device, revenue by
campaign, refund rate by product, and monthly revenue trend.

The goal is to make analytics safer and easier to trust: every answer comes from
a known template, shows the data table, explains the assumptions, and records an
audit trail.

## For A Technical Reader

The project implements a governed natural-language-to-analytics path over local
DuckDB data. A deterministic router maps supported questions to YAML-registered
SQL templates and metric contracts, validates date parameters, renders
parameterized SQL, executes read-only DuckDB queries, validates result shape and
metric ranges, explains the answer deterministically, and writes JSONL audit
events. The Streamlit dashboard wraps that same runtime with guided templates,
custom governed questions, charts, validation details, and data readiness checks.

## Dataset

The Maven Fuzzy Factory dataset contains ecommerce sessions, pageviews, orders, order items, refunds, products, and a data dictionary.

| File | Grain | Purpose |
| --- | --- | --- |
| `maven_fuzzy_factory_data_dictionary.csv` | One row per table field | Reference guide for tables and columns |
| `website_sessions.csv` | One row per website session | Traffic source, device, user, and session metadata |
| `website_pageviews.csv` | One row per pageview | Clickstream behavior within sessions |
| `orders.csv` | One row per completed order | Order-level conversion and revenue facts |
| `order_items.csv` | One row per purchased item | Product-level revenue, cost, and margin facts |
| `order_item_refunds.csv` | One row per refunded order item | Refund events and refund amounts |
| `products.csv` | One row per product | Product lookup table |

Place these CSV files locally in `data/raw/`. Raw CSVs are intentionally ignored by Git.

## Core Relationships

- `website_sessions.website_session_id = website_pageviews.website_session_id`
- `website_sessions.website_session_id = orders.website_session_id`
- `orders.order_id = order_items.order_id`
- `order_items.order_item_id = order_item_refunds.order_item_id`
- `products.product_id = orders.primary_product_id`
- `products.product_id = order_items.product_id`

Important grain rules:

- Never count pageviews as sessions.
- Never multiply revenue by joining pageviews directly to orders without grain control.
- Use `website_sessions` as the denominator source for conversion-rate metrics.
- Use `LEFT JOIN` from `website_sessions` to `orders` for conversion-rate calculations.
- Use `order_items` for product-level revenue and margin.
- Use `order_item_refunds` for refund metrics, joined through `order_item_id`.
- Treat refund-date attribution and order-date attribution as separate business policies.

## Architecture

The intended runtime path is:

1. Question classifier / ambiguity detector
2. Template matcher
3. Metric and template contract loader
4. SQL renderer
5. DuckDB executor
6. Programmatic validator
7. Answer explainer
8. Audit logger

Supporting infrastructure:

- Semantic metric registry
- SQL template registry
- Schema and data dictionary registry
- Validation rules
- Question-bank eval harness
- Optional Langfuse or LangSmith tracing later

## MVP Scope

The first MVP should support a small set of governed ecommerce questions such as traffic, conversion rate, revenue, product revenue, margin, refunds, and funnel metrics. Each supported question should map to a known metric contract and SQL template.

Out of scope for the initial scaffold:

- General CSV chatbot behavior
- LangGraph workflows
- Free-form SQL generation or execution
- Prompt-only metric definitions

## Staged Build Plan

1. Repository scaffold, governance docs, package metadata, ignore rules, and smoke test.
2. Dataset ingestion into DuckDB from CSV files in `data/raw/`.
3. Schema and data dictionary registry.
4. Semantic metric registry and metric contracts.
5. SQL template registry and renderer.
6. Runtime pipeline for supported questions.
7. Programmatic validators for grain, joins, assumptions, and result shape.
8. Audit logging and answer explanation.
9. Question-bank eval harness.
10. Optional Streamlit UI and tracing integrations.

## Setup

Create and activate a virtual environment, then install the project:

```bash
python -m venv .venv
python -m pip install -e .
```

Copy `.env.example` to `.env` when local configuration is needed.

Put the Maven Fuzzy Factory CSV files in `data/raw/`:

```text
data/raw/maven_fuzzy_factory_data_dictionary.csv
data/raw/website_sessions.csv
data/raw/website_pageviews.csv
data/raw/orders.csv
data/raw/order_items.csv
data/raw/order_item_refunds.csv
data/raw/products.csv
```

## Tests

Run tests from the project root:

```bash
python -m pytest
```

## Streamlit Dashboard

The repository includes a Streamlit interface for the approved analytics templates.
It uses the same governed runtime as the tests: natural-language routing,
parameter validation, SQL template rendering, DuckDB execution, result
validation, deterministic explanation, and audit logging.

Launch it from the project root:

```bash
python -m streamlit run app/dashboard.py --server.port 8512
```

The dashboard supports:

- Guided runs for the five approved templates.
- Custom governed questions that still route through the deterministic template matcher.
- Date range controls using the approved `start_date` and `end_date` parameters.
- Data readiness checks for raw CSV files and the processed DuckDB database.
- One-click DuckDB build when all required raw CSVs are present and the database is missing.
- KPI summaries, template-aware charts, result tables, validation checks, assumptions, rendered SQL, and audit status.

## Stage 3: Schema and Data Dictionary Registry

`src/semantic_layer/schema_registry.py` provides:

- `connect_db` — opens the DuckDB file (raises `FileNotFoundError` if missing)
- `list_tables` — returns all table names from the database
- `get_table_columns` — returns column names and DuckDB types for a table
- `load_data_dictionary` — reads all rows from `maven_fuzzy_factory_data_dictionary`
- `validate_expected_tables` — raises `ValueError` listing any missing expected tables
- `build_schema_registry` — returns a dict keyed by table name, each entry containing `table_name`, `grain`, `row_count` (live from DuckDB), `columns`, `allowed_join_keys`, and `dictionary_fields` when available

## Stage 4: Semantic Metric Registry

Metric definitions live in `src/semantic_layer/metrics.yaml` as versioned, governed contracts — not in prompts or ad hoc code.

Each contract specifies the metric ID, version, owner, business definition, grain, base table or component metrics, measure expression or formula, allowed dimensions, required tables, join paths, alignment rules, validation rules, assumptions, and approval status.

The 14 initial MVP metrics are:

| Metric | Grain | Base / Components |
| --- | --- | --- |
| `sessions` | session | `website_sessions` |
| `orders` | order | `orders` |
| `items_sold` | item | `order_items` |
| `gross_order_revenue` | order | `orders` |
| `gross_item_revenue` | item | `order_items` |
| `gross_profit` | item | `order_items` |
| `refund_amount` | refund | `order_item_refunds` |
| `net_revenue_after_refunds` | item | `order_items` + `order_item_refunds` |
| `conversion_rate` | session | `website_sessions` + `orders` |
| `revenue_per_session` | session | `website_sessions` + `orders` + `order_items` |
| `profit_per_session` | session | `website_sessions` + `orders` + `order_items` |
| `refund_rate` | item | `order_items` + `order_item_refunds` |
| `average_order_value` | order | `orders` |
| `items_per_order` | order | `orders` + `order_items` |

`src/semantic_layer/metric_registry.py` provides:

- `load_metric_contracts` — loads all contracts from YAML, keyed by `metric_id`
- `get_metric` — retrieves one contract by ID, raises `KeyError` if unknown
- `list_metrics` — returns sorted list of all metric IDs
- `validate_metric_contract` — validates a single contract dict
- `validate_all_metric_contracts` — validates the entire YAML file
- `get_metrics_by_table` — filters metrics by required table
- `get_metrics_by_grain` — filters metrics by grain

Metric definitions are intentionally separate from prompts. SQL templates will consume these contracts in Stage 5.

To validate all metric contracts:

```bash
python -m pytest tests/test_metric_registry.py
```

## Stage 5: SQL Template Registry and Renderer

Template contracts live in `src/templates/template_registry.yaml`. SQL files live in `src/templates/sql_templates/`.

Free-form SQL generation is out of scope. Every query must be backed by a versioned, approved template contract.

Each template declares its `template_id`, `version`, `owner`, `business_question`, `supported_metrics`, `required_tables`, `required_join_paths`, `parameters`, `validation_rules`, `assumptions`, and `status`. Templates consume metric contracts defined in Stage 4 (`src/semantic_layer/metrics.yaml`).

The five approved MVP templates are:

| Template ID | Business Question | Key Tables |
| --- | --- | --- |
| `conversion_by_channel` | Conversion rate by utm_source / utm_campaign | `website_sessions` LEFT JOIN `orders` |
| `conversion_by_device` | Conversion rate by device type | `website_sessions` LEFT JOIN `orders` |
| `revenue_by_campaign` | Revenue and AOV by utm_source / utm_campaign | `website_sessions` JOIN `orders` |
| `refund_rate_by_product` | Refund rate and refund amount by product | `order_items` LEFT JOIN `order_item_refunds`, JOIN `products` |
| `monthly_revenue_trend` | Monthly orders, revenue, and AOV trend | `orders` |

`src/templates/template_loader.py` provides:

- `load_template_registry` — loads all contracts from YAML, keyed by `template_id`
- `list_templates` — returns a sorted list of all template IDs
- `get_template` — retrieves one contract by ID, raises `KeyError` if unknown
- `validate_template_contract` — validates a single contract dict against required fields
- `validate_all_template_contracts` — validates every contract in the registry
- `get_template_sql` — loads the raw SQL string from the declared SQL file
- `validate_template_parameters` — validates a parameter dict against the template contract (required fields, unknown params, date format, enum values)
- `render_template_sql` — validates parameters then substitutes named placeholders in the SQL; SQL fragments are never accepted

Parameters are validated before substitution. Only declared parameters are accepted. Dates must be `YYYY-MM-DD`. Enum fields are checked against declared `allowed_values`. Arbitrary SQL fragments are rejected.

Stage 6 will connect these templates into the runtime question-answering pipeline.

## Current Limitations

- Runtime answers are limited to the approved template set.
- No tracing integration exists yet.
- Local CSVs must be supplied separately in `data/raw/`.
