"""Helper utilities for configuring raking targets in GUI contexts."""

from __future__ import annotations

from typing import Dict, Mapping


def parse_target_inputs(
    raw_values: Mapping[str, str],
) -> tuple[Dict[str, float], float]:
    """Parse raw string inputs into numeric targets normalised to 100.

    Parameters
    ----------
    raw_values:
        Mapping of category codes to the raw string values provided by the user.

    Returns
    -------
    tuple
        A tuple containing the normalised mapping (summing to 100) and the
        original total before normalisation.

    Raises
    ------
    ValueError
        If no numeric values are provided or if the values cannot be converted
        to floats or do not yield a positive total.
    """
    parsed: Dict[str, float] = {}
    for code, raw in raw_values.items():
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            parsed[str(code)] = float(text)
        except ValueError as err:  # pragma: no cover - defensive branch
            raise ValueError(f"Value for '{code}' is not numeric.") from err

    if not parsed:
        raise ValueError("At least one target value is required.")

    total = sum(parsed.values())
    if total <= 0:
        raise ValueError("Target values must sum to a positive number.")

    scale = 100.0 / total
    normalised = {code: value * scale for code, value in parsed.items()}
    return normalised, total


def format_target_values(values: Mapping[str, float]) -> str:
    """Return a compact string representation for a target mapping."""
    parts = [f"{code}: {value:.2f}" for code, value in values.items()]
    return ", ".join(parts)
