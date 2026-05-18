# Governed Ecommerce Analytics MVP

This project is the initial scaffold for a governed analytics application using the Maven Fuzzy Factory ecommerce and web analytics CSV dataset. The goal is to answer natural-language business questions through deterministic metric definitions, parameterized SQL templates, programmatic validation, audit logging, and an eval harness.

This is not a general CSV chatbot. The MVP should only answer supported business questions through governed metrics and approved templates.

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
- Streamlit UI implementation
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

## Current Limitations

- No SQL templates are implemented yet.
- No runtime question-answering path exists yet.
- No Streamlit UI exists yet.
- No tracing integration exists yet.
- Local CSVs must be supplied separately in `data/raw/`.

