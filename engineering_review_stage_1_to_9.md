# Maven Fuzzy Factory Governed Analytics MVP — Engineering Review

## 1. Executive Summary

The project appears coherent, testable, and aligned with the intended governed analytics MVP architecture. The implemented system is not a general CSV chatbot: supported questions are routed deterministically to named SQL templates, metric definitions live in a semantic layer, DuckDB execution is constrained to read-only SELECT statements, results are programmatically validated, explanations are deterministic, audit events are written, and a question-bank eval harness covers supported, clarify, and unsupported paths.

The strongest areas are governance boundaries, metric/template organization, test breadth, and data-grain awareness in the supported templates. The main gaps are MVP-shaped rather than fundamental: routing is keyword-based and uses broad default dates, validation mostly checks result shape/value sanity rather than proving SQL contract compliance, audit logs still store raw user questions and SQL previews, and production controls such as authentication, audit immutability, CI, and stronger parameter schemas are not yet present.

## 2. Overall Assessment

- Overall rating: 8/10
- Functional completeness rating: 8/10
- Architecture rating: 8/10
- Test quality rating: 8/10
- Governance readiness rating: 8/10
- Maintainability rating: 8/10

## 3. Implemented Architecture

The implemented runtime follows this actual path:

1. `src/runtime/router.py` maps natural-language questions to one of five approved template IDs, or to `clarify` / `unsupported`.
2. `src/runtime/pipeline.py` merges routed default parameters with caller-supplied parameters, loads the template contract, renders SQL, executes it in DuckDB, validates rows, builds a deterministic explanation, and writes an audit event.
3. `src/templates/template_registry.yaml` defines template contracts and `src/templates/sql_templates/*.sql` stores the SQL bodies.
4. `src/templates/template_loader.py` validates declared parameters and substitutes named placeholders.
5. `src/runtime/executor.py` rejects non-SELECT SQL and opens DuckDB in read-only mode.
6. `src/validation/validators.py` applies general and template-specific result validators.
7. `src/explanation/explainer.py` produces deterministic method, assumption, validation, and limitation text.
8. `src/audit/audit_logger.py` writes structured JSONL audit events with SQL hash and truncated SQL preview.
9. `src/evals/eval_runner.py` runs a YAML question bank and skips supported cases cleanly when DuckDB is missing.

This is close to the intended governed architecture:

`user question -> deterministic router -> template matcher -> metric/template contract loader -> SQL renderer -> DuckDB executor -> programmatic validator -> explanation -> audit logger -> eval harness`

The only meaningful deviation is that the metric contract loader is implemented and tested but is not deeply enforced in the runtime path beyond template assumptions and supported metric references.

## 4. Stage-by-Stage Review

| Stage | Status | Evidence | Strengths | Issues / Risks | Recommended Next Action |
|---|---|---|---|---|---|
| Stage 1 - repo scaffold, governance docs, package metadata | Implemented | `pyproject.toml`; `.gitignore`; `tests/test_project_structure.py` | Clear package metadata, pytest config, dependency list, ignored data artifacts. | `streamlit` and `python-dotenv` are already dependencies before UI/runtime use is visible in inspected code. Existing git state has untracked files. | Keep dependency list lean; add CI when ready. |
| Stage 2 - CSV ingestion into DuckDB | Implemented | `src/ingestion/load_csvs.py`; `tests/test_ingestion.py` | Required CSV list, table naming, row counts, creates processed DB path. | CSV paths are interpolated into SQL strings; low risk for local governed use, but not ideal if paths ever become user-controlled. | Use DuckDB parameter binding or stricter path validation for ingestion paths. |
| Stage 3 - schema and data dictionary registry | Implemented | `src/semantic_layer/schema_registry.py`; `tests/test_schema_registry.py` | Expected tables, grains, row counts, allowed joins, data dictionary extraction. | Table names are interpolated in `DESCRIBE` / count queries; only safe when called with trusted table names. | Add allowed-table validation to public schema lookup functions. |
| Stage 4 - semantic metric registry and contracts | Implemented | `src/semantic_layer/metrics.yaml`; `src/semantic_layer/metric_registry.py`; `tests/test_metric_registry.py` | Strong metric coverage, grain definitions, assumptions, join/alignment rules, validation rules. | Runtime does not yet cross-check rendered SQL against metric contracts. Some refund attribution wording differs between metrics and template contracts. | Add contract-to-template consistency checks and clarify refund attribution policy variants. |
| Stage 5 - SQL template registry and renderer | Implemented | `src/templates/template_registry.yaml`; `src/templates/template_loader.py`; SQL templates; `tests/test_template_loader.py` | Named templates, declared params, unknown param rejection, date format checks, file consistency checks. | Date validation checks format only, not calendar validity or `start_date < end_date`. Placeholder substitution is string-based. | Add date parsing, date ordering, and typed parameter rendering. |
| Stage 6 - runtime pipeline for supported questions | Implemented | `src/runtime/router.py`; `src/runtime/pipeline.py`; `src/runtime/executor.py`; `tests/test_runtime_pipeline.py` | Deterministic routing, no SQL for clarify/unsupported, read-only DuckDB execution, response includes SQL, assumptions, validation, audit fields. | Router is keyword-based and can misroute nuanced questions; default date range is hidden in router logic. Pipeline does not catch supported execution errors into structured `error` responses. | Add parameter extraction/clarification rules and structured error handling. |
| Stage 7 - programmatic validators | Implemented | `src/validation/validators.py`; `tests/test_validators.py` | Checks list/dict shape, NaN/infinite values, rate bounds, non-negative revenue/counts, orders <= sessions, refunds <= items. | Validators infer fields by substring and do not verify required columns, SQL joins, date attribution, or template contract compliance. Empty supported results pass. | Add strict expected-output schemas per template and SQL/static contract validators. |
| Stage 8 - audit logging and deterministic explanations | Implemented | `src/audit/audit_logger.py`; `src/explanation/explainer.py`; related tests | JSONL audit, timestamp, SQL hash, truncated SQL preview, validation summary, deterministic explanation for ok/clarify/unsupported. | Audit logs include raw questions and SQL previews; audit integrity is append-only file based but not tamper-evident. | Redact/minimize audit fields and add tamper-evident or centralized audit storage for production. |
| Stage 9 - question-bank eval harness | Implemented | `src/evals/question_bank.yaml`; `src/evals/eval_runner.py`; `tests/test_eval_runner.py` | Covers five supported, three clarify, four unsupported cases; skips executable cases if DB missing; checks route/template/status/validation. | Supported evals assert high-level behavior, not metric numeric correctness or full expected output schemas. | Add fixture-backed deterministic expected results and regression thresholds. |

## 5. Functional Correctness Findings

### Critical

No critical defects were found in the inspected MVP scope.

### High

**Finding:** Runtime validation does not prove that SQL followed the governed contract.  
**Evidence from code/tests:** `validate_result` in `src/validation/validators.py` validates returned rows, not rendered SQL. Template contract tests check some static facts such as no `website_pageviews` use and left joins, but there is no runtime SQL-contract validator.  
**Why it matters:** A template could drift to an unsafe join or wrong denominator while still returning plausible rows that pass value checks.  
**Recommended fix:** Add static SQL validation per template before execution: required tables, forbidden tables, required join path, required denominator/numerator expressions, date field, and expected output columns.

**Finding:** Date parameters are format-checked but not semantically validated.  
**Evidence from code/tests:** `validate_template_parameters` checks dates with `^\d{4}-\d{2}-\d{2}$`; tests reject bad formatting but not invalid calendar dates or reversed ranges.  
**Why it matters:** Values such as `2024-99-99`, or `end_date` before `start_date`, can reach DuckDB and produce confusing errors or empty outputs.  
**Recommended fix:** Parse dates with `datetime.date.fromisoformat` and enforce `start_date < end_date` for templates with ranges.

### Medium

**Finding:** The deterministic router is useful for MVP but brittle.  
**Evidence from code/tests:** `route_question` uses lowercase keyword checks for terms such as conversion, device, campaign, refund, monthly, and revenue.  
**Why it matters:** Supported business questions phrased differently may be rejected or routed to the wrong template, while ambiguous questions that include a metric word may skip clarification.  
**Recommended fix:** Add an explicit intent registry with synonyms, negative examples, and ambiguity checks tied to eval cases.

**Finding:** Metric contracts are not fully enforced by the runtime.  
**Evidence from code/tests:** `src/semantic_layer/metrics.yaml` is robust and tested, while `answer_question` loads template assumptions but does not load or validate each supported metric contract.  
**Why it matters:** The semantic layer can drift from template SQL without being detected at execution time.  
**Recommended fix:** Add a template-to-metric consistency test and runtime metadata attachment for metric definitions used in each answer.

**Finding:** Audit logging is sufficient for traceability but not yet production-grade.  
**Evidence from code/tests:** Audit events include question, parameters, row count, validation summary, assumptions, SQL hash, SQL preview, and timestamp.  
**Why it matters:** Raw questions may contain sensitive information, SQL previews can reveal schema/business logic, and JSONL files can be modified without detection.  
**Recommended fix:** Redact or hash raw questions where appropriate, consider removing SQL previews in production, and add append-only/tamper-evident storage.

**Finding:** Refund attribution policy needs sharper separation.  
**Evidence from code/tests:** `refund_amount` and `net_revenue_after_refunds` metric assumptions mention refund-event-date attribution, while `refund_rate_by_product` template explicitly uses item sale date attribution.  
**Why it matters:** Both policies can be valid, but mixing them without a first-class policy dimension can confuse users and future developers.  
**Recommended fix:** Add explicit attribution policy fields to metric and template contracts, then validate compatibility.

### Low

**Finding:** Empty result sets pass validation for supported templates.  
**Evidence from code/tests:** `test_empty_rows_passes_general`, `test_revenue_by_campaign_empty_rows_passes`, and `test_monthly_revenue_trend_empty_passes`.  
**Why it matters:** This is acceptable for no-data date ranges, but it may hide a broken filter or bad date range.  
**Recommended fix:** Keep empty rows allowed, but return a warning when a supported template returns zero rows for a broad default range.

**Finding:** Some SQL/path interpolation exists in trusted internal code.  
**Evidence from code/tests:** Ingestion uses formatted SQL for CSV paths; schema registry interpolates table names.  
**Why it matters:** Low risk in current local workflow, but risky if exposed through UI inputs later.  
**Recommended fix:** Whitelist table names and use safer DuckDB APIs/parameterization where possible.

## 6. Data Grain and Metric Safety Findings

The supported templates are generally safe for the Maven Fuzzy Factory grains:

- Sessions: conversion templates count `COUNT(DISTINCT ws.website_session_id)` from `website_sessions`, not pageviews.
- Orders: order/revenue templates use `orders` and `COUNT(DISTINCT o.order_id)`.
- Pageviews: MVP templates and tests avoid `website_pageviews`, reducing fanout risk.
- Product/item grain: refund rate uses `order_items` as the base, joins products for product name, and left joins refunds through `order_item_id`.
- Revenue: campaign and monthly revenue use `orders.price_usd`, which matches gross order revenue contracts. Product-level revenue is defined in metrics but not currently exposed through a supported template.
- Refunds: refund rate uses item sale date attribution in the template, while some semantic refund contracts describe refund-event-date attribution. This is the main policy ambiguity.

Specific risks:

- The validators cannot detect a future unsafe pageview-to-order fanout if row values remain plausible.
- `refund_rate_by_product.sql` uses `COUNT(oir.order_item_id)` rather than `COUNT(DISTINCT oir.order_item_id)`. The contract assumes at most one refund row per item, so this is coherent under that assumption but could overcount if source data violates it.
- Revenue-per-session and profit-per-session metrics exist in contracts but have no corresponding supported template in the inspected runtime, so their grain safety is defined but not exercised.

## 7. SQL Template and Runtime Safety Findings

SQL safety is strong for an MVP:

- SQL comes from files under `src/templates/sql_templates`, not from free-form generation.
- Template IDs are resolved through `template_registry.yaml`.
- Unknown parameters are rejected.
- Date parameters are constrained to `YYYY-MM-DD` format.
- The executor rejects statements whose non-comment prefix is not `SELECT`.
- DuckDB is opened with `read_only=True`.

Remaining gaps:

- Placeholder substitution is string replacement. This is acceptable for current date-only parameters, but it should be replaced or wrapped with typed escaping before adding string filters.
- The non-SELECT guard is a simple prefix check after stripping full-line comments. It blocks obvious writes but is not a complete SQL parser.
- Template/registry consistency is tested for presence and some business rules, but there is no comprehensive parser-based check of selected columns, joins, and date predicates.
- Calendar validity and date ordering are not enforced.

## 8. Validation Layer Findings

The validation layer covers important row-level sanity checks:

- rows must be a list of dicts
- numeric NaN and infinite values fail
- conversion rates and refund rates must be between 0 and 1
- orders cannot exceed sessions in conversion outputs
- refund counts cannot exceed item/order counts
- revenue-like fields must be non-negative
- monthly date/month/time fields cannot be null

Weaknesses:

- Field matching is substring-based, which can create false positives or false negatives as output schemas evolve.
- Required output columns are not enforced explicitly per template.
- Empty results pass with no warning.
- Validation does not inspect SQL or execution plans, so grain violations can evade it.
- The `parameters` argument is currently unused, so validators do not check parameter-sensitive expectations.

Recommended direction: add per-template schemas with required columns, types, nullable rules, min/max constraints, and optional no-data warnings; pair this with static SQL contract validation.

## 9. Audit Logging and Explanation Findings

Audit logging is useful and deterministic:

- `build_audit_event` records status, route type, template ID, parameters, row count, validation status, validation summary, assumptions, SQL hash, SQL preview, and question.
- `write_audit_event` creates parent directories and appends JSONL with UTC timestamp.
- Clarify and unsupported paths are logged with null SQL hash/preview.
- Tests verify hashing, truncation, append behavior, timestamps, and null SQL fields for non-execution paths.

Risks:

- Audit logs include raw user questions, which can leak sensitive business context.
- SQL previews are truncated but still reveal query logic and table/field names.
- File-based JSONL logs are easy to edit or delete.
- Audit events do not include a returned trace ID field distinct from path/logged status; the response includes `audit_logged` and `audit_path`, but not a stable event ID.

Explanations are deterministic and appropriately restrained. They state the governed template, row count, assumptions, method, validation summary, and limitations without inventing business interpretation.

## 10. Eval Harness Findings

The eval harness is valuable for regression testing:

- Question bank includes five supported cases, three clarify cases, and four unsupported cases.
- Clarify and unsupported cases run without DuckDB.
- Supported cases skip cleanly if DuckDB is missing.
- Checks cover expected status, route type, template ID, SQL execution/no execution, and validation status.

Gaps:

- Supported cases do not assert expected row values, result columns, or numeric invariants beyond pipeline validation.
- Eval reporting is programmatic but not yet packaged as a user-friendly report or CI artifact.
- The question bank is still small and mostly direct phrasing; it should include paraphrases, boundary cases, and deliberately ambiguous metric requests.

## 11. Testing Results

- Command run: `python -m pytest`
- Result: passed
- Exact result observed: `193 passed in 5.37s`
- Failures: none
- Skipped tests: none observed in this environment

Interpretation: the inspected test suite is broad for an MVP and exercises all nine stages. Because no tests skipped, the local DuckDB-backed smoke tests ran successfully. The remaining test gap is not breadth of modules, but depth of semantic verification: more tests should prove SQL contract compliance, expected output schemas, date validation, attribution policy compatibility, and fixture-backed numeric correctness.

## 12. Security and Governance Review

SQL execution governance is good for the current scope. The runtime uses template-backed SQL and rejects non-SELECT statements before opening a read-only DuckDB connection. The system does not expose free-form SQL execution in the inspected code.

Data leakage risk is moderate for audit logs. Query result rows are not written into audit events, which is good. However, raw questions, parameters, assumptions, SQL hashes, and SQL previews are logged. This is likely acceptable for a local MVP demonstration but should be tightened for production.

Raw data handling appears appropriate from inspected files. `.gitignore` excludes `*.csv`, DuckDB/database files, and `data/raw/*` / `data/processed/*` while preserving `.gitkeep` files. Raw CSV contents and generated DuckDB files were not inspected during this review.

Deterministic control boundaries are strong: no LLM reasoning is used for metric definitions, SQL generation, validation, or explanations in the inspected implementation.

## 13. Maintainability and Extensibility Review

Adding a new metric is straightforward: add a contract to `src/semantic_layer/metrics.yaml`, then add metric registry tests. The metric registry is small and explicit.

Adding a new SQL template is also straightforward: add a SQL file, register it in `template_registry.yaml`, add a route, add validator behavior if needed, and add tests/eval cases.

Adding supported questions currently requires editing keyword logic in `src/runtime/router.py`. This is simple but may become harder to manage as coverage grows. A data-driven intent registry would scale better.

Adding validators is easy because `validators.py` has template-specific checker functions behind `_TEMPLATE_CHECKERS`. The next maintainability improvement is moving expected columns and constraints into declarative per-template validation contracts.

Adding eval cases is easy through `question_bank.yaml`. The harness already supports skipped SQL cases and non-SQL paths.

Adding Streamlit later should be feasible because `answer_question` returns a structured response containing status, route, parameters, SQL, rows, assumptions, validation, explanation, and audit fields. Before UI exposure, the project should improve parameter validation, user-facing errors, and audit redaction.

## 14. Production Readiness Gaps

- Authentication and authorization are absent.
- Audit logs are file-based and not tamper-evident.
- Raw question logging needs a privacy/redaction policy.
- SQL preview logging should be configurable or disabled in production.
- Date and parameter schemas need stronger validation.
- Runtime should return structured errors instead of allowing supported-path exceptions to propagate.
- Metric contracts should be versioned and enforced against template SQL.
- Validation needs strict output schemas and SQL contract checks.
- Evals need fixture-backed numeric correctness cases.
- CI workflow is not visible in inspected scope.
- Observability/tracing is scaffolded but not implemented.
- Streamlit UI hardening is not yet applicable from inspected code.
- Deployment configuration is not present.

## 15. Prioritized Recommendations

### 1. Must fix before demo

1. Add explicit user-facing handling for supported-path execution errors, especially missing/invalid DuckDB and invalid parameters.
2. Add date semantic validation: valid calendar dates and `start_date < end_date`.
3. Add a stable audit trace/event ID to each response.

### 2. Should fix soon

1. Add static SQL contract validation for required joins, forbidden tables, denominator/numerator expressions, date fields, and required output columns.
2. Add per-template result schemas instead of substring-based field detection.
3. Enforce metric-template consistency so template SQL cannot drift from semantic metric contracts.
4. Clarify refund attribution policy in first-class contract fields.
5. Expand evals with paraphrases, ambiguous cases, and fixture-backed expected results.

### 3. Nice to improve later

1. Move router intent rules into configuration.
2. Add CI to run `python -m pytest`.
3. Add configurable audit redaction and production audit storage.
4. Build eval result reporting for demos.
5. Add Streamlit UI after parameter/error handling is stronger.

## 16. Fact Check List

- [x] No claim in this review depends on files not inspected.
- [x] No production-readiness claim is overstated.
- [x] No unsupported assumptions are presented as facts.
- [x] Test results are reported exactly.
- [x] Raw data was not unnecessarily inspected.
- [x] No source code changes were made.
- [x] The only file intentionally created or modified was `docs/engineering_review_stage_1_to_9.md`.

## 17. Reflection

The review is strongest on architecture, template governance, validation behavior, audit/explanation behavior, and tests because those files were directly inspected. It is less certain on full end-to-end data correctness because raw CSV contents and generated DuckDB internals were intentionally not inspected. The passing live DuckDB tests show the pipeline works locally, but they do not prove every metric value against independently computed fixtures.

Some findings depend on incomplete test coverage: SQL contract drift, refund attribution ambiguity, and date semantic validation are risks inferred from inspected code and tests, not observed runtime failures.

This review should be followed by a fix pass focused on parameter validation, SQL contract validation, stricter result schemas, and audit trace IDs before a stakeholder demo.

## 18. Cognitive Verification

- Findings are supported by inspected implementation files and tests.
- Severity levels distinguish MVP gaps from true defects.
- Recommendations are actionable and scoped.
- No hallucinated files, modules, or test results are included.
- The review distinguishes between production readiness gaps and current MVP correctness.
- Raw CSV contents and generated DuckDB files were not inspected.
- Source code was not modified during this review.
