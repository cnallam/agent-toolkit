"""
Google-ADK FunctionTool for the PayPal REST API's
"""

from __future__ import annotations

import inspect
from typing import (
    Any, Dict, List, Optional, Union, Annotated, Literal,
    get_origin, get_args,
)

from pydantic import BaseModel, ConfigDict, create_model
from pydantic.networks import AnyUrl, HttpUrl
from google.adk.tools import FunctionTool, ToolContext
from ..shared.api import PayPalAPI


# ────────────────────────────────────────────────────────────────────────────
# 1)  Annotation simplifier
# ────────────────────────────────────────────────────────────────────────────
def _simplify_basemodel(model_cls: type[BaseModel]) -> type[BaseModel]:
    """Return a *new* model class whose field annotations are ADK-friendly."""
    fields: dict[str, tuple[Any, Any]] = {}
    for name, field in model_cls.model_fields.items():          # type: ignore[attr-defined]
        ann = _simplify_annotation(field.annotation)            
        default = inspect._empty if field.is_required() else field.default
        fields[name] = (ann, default)

    return create_model(                                        # type: ignore[call-arg]
        f"Simplified{model_cls.__name__}",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


def _simplify_annotation(tp):  # noqa: ANN001
    """
    Collapse rich typing / Pydantic constructs to primitives ADK accepts.

    Literal       → str
    Annotated     → underlying type
    constr / URLs → str
    BaseModel     → *simplified clone* (recursively processed)
    Containers    → same container with inner types simplified
    """
    # 0) URLs and constrained primitives → plain primitives
    if isinstance(tp, type):
        if issubclass(tp, (AnyUrl, HttpUrl)):
            return str
        # v2 no longer has ConstrainedStr; use a generic catch‑all
        if issubclass(tp, str) and tp is not str:
            return str
        if issubclass(tp, int) and tp is not int:
            return int
        if issubclass(tp, float) and tp is not float:
            return float


    origin = get_origin(tp)
    args = get_args(tp)

    # 1) Optional[X] (Union[X, None])
    if origin is Union and len(args) == 2 and type(None) in args:
        non_null = next(a for a in args if a is not type(None))
        return Optional[_simplify_annotation(non_null)]         # type: ignore[arg-type]

    # 2) Annotated[base, …]  → base
    if origin is Annotated:
        return _simplify_annotation(args[0])

    # 3) Literal[...] → str
    if origin is Literal:
        return str

    # 4) Containers ---------------------------------------------------------
    if origin in (list, List):
        return List[_simplify_annotation(args[0])]              # type: ignore[arg-type]
    if origin in (dict, Dict):
        key_t, val_t = args or (str, Any)
        return Dict[
            _simplify_annotation(key_t), _simplify_annotation(val_t)  # type: ignore[arg-type]
        ]

    # 5) Nested Pydantic models --------------------------------------------
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return _simplify_basemodel(tp)

    # 6) Already simple (str, int, float, bool, Any…)
    return tp


# ────────────────────────────────────────────────────────────────────────────
# 2)  Public factory
# ────────────────────────────────────────────────────────────────────────────
def PayPalTool(api: PayPalAPI, spec: Dict[str, Any]) -> FunctionTool:  # noqa: N802
    """
    Create an ADK FunctionTool for **one** PayPal REST operation.

    `spec` must contain:
    • method        - PayPal REST method name (“create_order”)
    • description   - Human-readable description
    • args_schema   - Pydantic-v2 model *class* describing the request body
    """
    method_name: str = spec["method"]
    schema_model = spec["args_schema"]
    description: str = spec["description"]

    # ── runtime implementation ────────────────────────────────────────────
    async def _tool_impl(tool_context: ToolContext, **kwargs):  # noqa: ANN001
        # kwargs already validated / converted by ADK
        return api.run(method_name, kwargs)

    _tool_impl.__name__ = method_name
    _tool_impl.__doc__ = description

    # ── build signature with simplified types ─────────────────────────────
    parameters: List[inspect.Parameter] = []
    for name, field in schema_model.model_fields.items():       # type: ignore[attr-defined]
        parameters.append(
            inspect.Parameter(
                name=name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=_simplify_annotation(field.annotation),
                default=inspect._empty,          # ADK dislikes defaults
            )
        )

    # Hidden ADK context (not shown to LLM)
    parameters.append(
        inspect.Parameter(
            name="tool_context",
            kind=inspect.Parameter.KEYWORD_ONLY,
            annotation=ToolContext,
            default=inspect._empty,
        )
    )

    _tool_impl.__signature__ = inspect.Signature(parameters)

    # ── wrap & return ─────────────────────────────────────────────────────
    return FunctionTool(
        func=_tool_impl
    )
