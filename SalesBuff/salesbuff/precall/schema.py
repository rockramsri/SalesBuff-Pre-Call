"""Pydantic <-> Tavily Research output_schema helpers.

Tavily Research accepts a small JSON-Schema subset for ``output_schema``:
top-level ``properties`` (+ optional ``required``), where each property has a
``type`` (object/string/integer/number/array), a ``description``, and ``items``
/ nested ``properties`` for arrays and objects.

These helpers convert a Pydantic model into that subset (resolving ``$ref`` and
flattening ``Optional[...]`` fields) and validate a research response back into
the same model.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

# Tavily output_schema allows only these property types. Booleans are emitted as
# "string"; Pydantic coerces "true"/"false"/"yes"/"no" back to bool on validate.
_KEEP = ("object", "string", "integer", "number", "array")


def _resolve(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if ref:
        return defs.get(ref.split("/")[-1], {})
    return node


def _convert(node: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    node = _resolve(node, defs)

    # Optional[T] -> Pydantic emits {"anyOf": [{type: T}, {type: "null"}]}
    any_of = node.get("anyOf")
    if any_of:
        non_null = [b for b in any_of if b.get("type") != "null"]
        if non_null:
            converted = _convert(non_null[0], defs)
            if node.get("description"):
                converted.setdefault("description", node["description"])
            return converted

    node_type = node.get("type")
    out: dict[str, Any] = {"type": node_type if node_type in _KEEP else "string"}

    if node_type == "object":
        out["properties"] = {
            name: _property(defn, defs)
            for name, defn in (node.get("properties") or {}).items()
        }
    elif node_type == "array":
        out["items"] = _convert(node.get("items") or {}, defs)

    if node.get("description"):
        out["description"] = node["description"]
    return out


def _property(defn: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    converted = _convert(defn, defs)
    # Tavily wants a description on every property; fall back to a placeholder.
    converted.setdefault("description", defn.get("description", ""))
    return converted


def pydantic_to_tavily_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs = raw.get("$defs", {})
    properties = {
        name: _property(defn, defs)
        for name, defn in (raw.get("properties") or {}).items()
    }
    schema: dict[str, Any] = {"properties": properties}
    # Tavily requires at least one required key; default to the first property.
    required = raw.get("required") or ([next(iter(properties))] if properties else [])
    if required:
        schema["required"] = required
    return schema


def validate_research(content: Any, model: type[BaseModel]) -> BaseModel | None:
    """Validate Tavily research content (dict or JSON string) into ``model``."""
    validated, _ = validate_research_detail(content, model)
    return validated


def validate_research_detail(
    content: Any, model: type[BaseModel]
) -> tuple[BaseModel | None, str | None]:
    """Validate research content; return ``(model, error_message)``."""
    if content is None:
        return None, "content is None"
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (ValueError, TypeError) as exc:
            return None, f"content is not valid JSON: {exc}"
    if not isinstance(content, dict):
        return None, f"content is {type(content).__name__}, expected dict"
    try:
        return model.model_validate(content), None
    except ValidationError as exc:
        errors = exc.errors()
        preview = errors[:3]
        return None, f"schema validation failed ({model.__name__}): {preview}"
