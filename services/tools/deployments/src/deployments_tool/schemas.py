"""JSON Schema documents for get_recent_deployments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from deployments_tool.errors import ToolError, ToolValidationError
from deployments_tool.limits import ToolLimits

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
_FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER


def _load(name: str) -> dict[str, Any]:
    loaded: Any = json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError(f"{name} must be a JSON object")
    return loaded


def recent_deployments_input_schema(limits: ToolLimits) -> dict[str, Any]:
    """Return the input schema with the active lookback cap."""
    schema = _load("get_recent_deployments.input.json")
    schema["properties"]["lookback_hours"]["maximum"] = limits.max_lookback_hours
    return schema


def recent_deployments_output_schema(limits: ToolLimits) -> dict[str, Any]:
    """Return the output schema with the active deployment-count cap."""
    schema = _load("get_recent_deployments.output.json")
    schema["properties"]["items"]["maxItems"] = limits.max_deployments
    return schema


def parse_model(payload: Any, schema: dict[str, Any], model: type[BaseModel]) -> Any:
    """Reject anything the published schema or the Pydantic model does not allow."""
    if not isinstance(payload, dict):
        raise ToolValidationError("tool input must be a JSON object")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        raise ToolValidationError(errors[0].message)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ToolValidationError(str(exc)) from exc


def validate_output(model: BaseModel, schema: dict[str, Any]) -> dict[str, Any]:
    """Return the JSON form of `model` after checking it against the output schema."""
    instance = model.model_dump(mode="json")
    validator = Draft202012Validator(schema, format_checker=_FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        raise ToolError(f"tool output failed schema validation: {errors[0].message}")
    return instance
