from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "quantipy" / "gui" / "target_utils.py"


spec = importlib.util.spec_from_file_location("target_utils", MODULE_PATH)
assert spec and spec.loader  # pragma: no cover - test guard
target_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target_utils)

parse_target_inputs = target_utils.parse_target_inputs
format_target_values = target_utils.format_target_values


def test_parse_target_inputs_normalises_to_hundred():
    normalised, total = parse_target_inputs({"1": "60", "2": "40"})
    assert math.isclose(total, 100.0)
    assert math.isclose(normalised["1"], 60.0)
    assert math.isclose(normalised["2"], 40.0)


def test_parse_target_inputs_rescales_when_total_differs():
    normalised, total = parse_target_inputs({"1": "30", "2": "70", "3": "100"})
    assert math.isclose(total, 200.0)
    assert math.isclose(sum(normalised.values()), 100.0)
    expected = {"1": 15.0, "2": 35.0, "3": 50.0}
    for code, value in expected.items():
        assert math.isclose(normalised[code], value)


def test_parse_target_inputs_rejects_missing_values():
    with pytest.raises(ValueError):
        parse_target_inputs({"1": "", "2": "   "})


@pytest.mark.parametrize("invalid", ["abc", None])
def test_parse_target_inputs_rejects_non_numeric(invalid):
    with pytest.raises(ValueError):
        parse_target_inputs({"1": invalid})


def test_format_target_values():
    formatted = format_target_values({"A": 33.3333, "B": 66.6667})
    assert formatted == "A: 33.33, B: 66.67"
