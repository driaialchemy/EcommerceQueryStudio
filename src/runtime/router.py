"""Deterministic MVP router: maps natural-language questions to template IDs."""

from __future__ import annotations

_DEFAULT_START = "2012-01-01"
_DEFAULT_END = "2015-12-31"


def _default_params() -> dict:
    return {"start_date": _DEFAULT_START, "end_date": _DEFAULT_END}


def route_question(question: str) -> dict:
    """Map a natural-language question to a template route deterministically.

    Returns a dict with keys:
        route_type: "template" | "clarify" | "unsupported"
        template_id: str | None
        confidence: float
        reason: str
        extracted_parameters: dict
    """
    q = question.lower()

    # Ambiguity check before routing — vague performance questions
    _ambiguous_phrases = ("best channel", "most profitable", "performance")
    _has_metric = any(w in q for w in ("conversion", "revenue", "refund", "orders", "sessions"))
    if any(phrase in q for phrase in _ambiguous_phrases) and not _has_metric:
        return {
            "route_type": "clarify",
            "template_id": None,
            "confidence": 0.5,
            "reason": (
                "Question is ambiguous — it references performance or profitability "
                "without specifying a metric (conversion rate, revenue, refund rate, etc.)."
            ),
            "extracted_parameters": {},
        }

    # Template routing — order matters: more specific patterns first
    if "conversion" in q and "device" in q:
        return {
            "route_type": "template",
            "template_id": "conversion_by_device",
            "confidence": 0.95,
            "reason": "Question references conversion and device type.",
            "extracted_parameters": _default_params(),
        }

    if "conversion" in q and ("channel" in q or "source" in q or "campaign" in q):
        return {
            "route_type": "template",
            "template_id": "conversion_by_channel",
            "confidence": 0.95,
            "reason": "Question references conversion and traffic channel.",
            "extracted_parameters": _default_params(),
        }

    if "refund" in q and ("product" in q or "item" in q):
        return {
            "route_type": "template",
            "template_id": "refund_rate_by_product",
            "confidence": 0.95,
            "reason": "Question references refunds and products.",
            "extracted_parameters": _default_params(),
        }

    if ("monthly" in q and "revenue" in q) or "revenue trend" in q:
        return {
            "route_type": "template",
            "template_id": "monthly_revenue_trend",
            "confidence": 0.95,
            "reason": "Question references monthly revenue trend.",
            "extracted_parameters": _default_params(),
        }

    if "revenue" in q and ("campaign" in q or "channel" in q or "source" in q):
        return {
            "route_type": "template",
            "template_id": "revenue_by_campaign",
            "confidence": 0.90,
            "reason": "Question references revenue and traffic campaign or channel.",
            "extracted_parameters": _default_params(),
        }

    return {
        "route_type": "unsupported",
        "template_id": None,
        "confidence": 0.0,
        "reason": (
            "No supported template matches this question. "
            "Supported topics: conversion by channel, conversion by device, "
            "revenue by campaign, refund rate by product, monthly revenue trend."
        ),
        "extracted_parameters": {},
    }
