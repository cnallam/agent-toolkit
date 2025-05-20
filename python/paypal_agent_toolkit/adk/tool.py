"""
Google ADK FunctionTool for a PayPal REST API's.
"""

from __future__ import annotations

import inspect
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Annotated,
    Literal,
    get_args,
    get_origin,
)

from pydantic import BaseModel
from pydantic.networks import AnyUrl, HttpUrl 
from google.adk.tools import FunctionTool, ToolContext

# adjust this import to your project structure
from ..shared.api import PayPalAPI


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _simplify_annotation(tp):  # noqa: ANN001
    """
    Convert rich typing / Pydantic constructs into ADK-friendly types.

    * Literal["USD"]      -> str
    * Annotated[str, …]   -> str
    * constr/min|max      -> str
    * BaseModel subclass  -> dict
    * List[X]             -> list[{simplified X}]
    * Optional[X]         -> Optional[{simplified X}]
    """

    if isinstance(tp, type) and issubclass(tp, (AnyUrl, HttpUrl)):
        return str
    origin = get_origin(tp)

    # Optional[...]  (Union[X, None])
    if origin is Union and type(None) in get_args(tp):
        non_null = next(a for a in get_args(tp) if a is not type(None))
        return Optional[_simplify_annotation(non_null)]  # type: ignore[arg-type]

    # Annotated[base, ...]  -> base
    if origin is Annotated:
        base = get_args(tp)[0]
        return _simplify_annotation(base)

    # Literal[...]  -> str
    if origin is Literal:
        return str

    # Containers ------------------------------------------------------------
    if origin in (list, List):
        inner = _simplify_annotation(get_args(tp)[0])
        return List[inner]  # type: ignore[arg-type]

    if origin in (dict, Dict):
        key_t, val_t = get_args(tp) or (str, Any)
        return Dict[_simplify_annotation(key_t), _simplify_annotation(val_t)]  # type: ignore[arg-type]

    # Pydantic BaseModel -> dict
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return dict

    return tp


# --------------------------------------------------------------------------- #
# Factory                                                                     #
# --------------------------------------------------------------------------- #
def PayPalTool(api: PayPalAPI, spec: Dict[str, Any]) -> FunctionTool:  # noqa: N802
    """
    Build an ADK FunctionTool for one PayPal REST operation.

    Parameters
    ----------
    api
        Active `PayPalAPI` wrapper.
    spec
        Dict with keys: ``method`` (str), ``description`` (str),
        ``args_schema`` (Pydantic model class).

    Returns
    -------
    google.adk.tools.FunctionTool
    """
    method_name: str = spec["method"]
    schema_model = spec["args_schema"]          # Pydantic v2 model **class**
    description: str = spec["description"]

    # ------------------------------------------------------------------ #
    # Runtime implementation                                             #
    # ------------------------------------------------------------------ #
    async def _tool_impl(tool_context: ToolContext, **kwargs):  # noqa: ANN001
        """Delegate to PayPalAPI.run (auto-generated)."""
        return api.run(method_name, kwargs)

    _tool_impl.__name__ = method_name
    _tool_impl.__doc__ = description

    # ------------------------------------------------------------------ #
    # Build an ADK‑friendly *Signature*                                  #
    # ------------------------------------------------------------------ #
    parameters: List[inspect.Parameter] = []

    for field_name, field in schema_model.model_fields.items():  # type: ignore[attr-defined]
        parameters.append(
            inspect.Parameter(
                name=field_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=_simplify_annotation(field.annotation),
                default=inspect._empty,      # ADK dislikes default values
            )
        )

    # Hidden ADK execution context (not exposed to the LLM)
    parameters.append(
        inspect.Parameter(
            name="tool_context",
            kind=inspect.Parameter.KEYWORD_ONLY,
            annotation=ToolContext,
            default=inspect._empty,
        )
    )

    _tool_impl.__signature__ = inspect.Signature(parameters)

    # ------------------------------------------------------------------ #
    # Wrap & return                                                      #
    # ------------------------------------------------------------------ #
    return FunctionTool(func=_tool_impl)
