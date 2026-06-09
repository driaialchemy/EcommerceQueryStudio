from datetime import date

import pandas as pd

from app.dashboard import TEMPLATE_OPTIONS, _build_parameters, _response_frame
from src.runtime.router import route_question


def test_dashboard_template_questions_route_to_expected_templates() -> None:
    for option in TEMPLATE_OPTIONS.values():
        route = route_question(option["question"])

        assert route["route_type"] == "template"
        assert route["template_id"] == option["template_id"]


def test_build_parameters_uses_iso_dates() -> None:
    params = _build_parameters(date(2012, 1, 1), date(2012, 2, 1))

    assert params == {"start_date": "2012-01-01", "end_date": "2012-02-01"}


def test_response_frame_handles_empty_rows() -> None:
    frame = _response_frame({"rows": []})

    assert isinstance(frame, pd.DataFrame)
    assert frame.empty
