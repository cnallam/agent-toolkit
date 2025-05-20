from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, List
from google.adk.tools import ToolContext
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.adk.tools.openapi_tool.openapi_spec_parser.rest_api_tool import RestApiTool
from ..shared.api import PayPalAPI
import json, pprint as _pprint

def _json_schema_to_oas3(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Draft-2020-12 → OpenAPI 3.0 (Vertex/Gemini-friendly)."""
    if not isinstance(schema, Mapping):
        print("Not an instance of schema")
        return schema

    schema = deepcopy(schema)          # work on our own copy

    # 1) Nullable shortcut ---------------------------------------------------
    t = schema.get("type")
    if isinstance(t, list) and "null" in t:
        schema["nullable"] = True
        schema["type"] = next((x for x in t if x != "null"), None)
        if schema["type"] is None:
            schema.pop("type")

    # 2) Collapse simple anyOf + null ---------------------------------------
    if "anyOf" in schema:
        variants: List[Dict[str, Any]] = schema["anyOf"]
        if len(variants) == 2 and any(v.get("type") == "null" for v in variants):
            non_null = next(v for v in variants if v.get("type") != "null")
            non_null = _json_schema_to_oas3(non_null)
            non_null["nullable"] = True
            schema = non_null                          # replace whole node
        else:
            # keep only anyOf & description
            desc = schema.get("description")
            schema = {
                "anyOf": [_json_schema_to_oas3(v) for v in variants]
            }
            if desc:
                schema["description"] = desc

    # 3) Flatten allOf -------------------------------------------------------
    if "allOf" in schema:
        flat = {}
        for part in schema.pop("allOf"):
            flat.update(_json_schema_to_oas3(part))
        schema.update(flat)

    # 4) oneOf → keep first variant (or whatever rule you like) -------------
    if "oneOf" in schema:
        schema.update(_json_schema_to_oas3(schema["oneOf"][0]))
        schema.pop("oneOf")

    # 5) Recurse into properties/items --------------------------------------
    if "properties" in schema:
        schema["properties"] = {
            k: _json_schema_to_oas3(v) for k, v in schema["properties"].items()
        }
    if "items" in schema:
        if isinstance(schema["items"], list):
            schema["items"] = [_json_schema_to_oas3(i) for i in schema["items"]]
        else:
            schema["items"] = _json_schema_to_oas3(schema["items"])

    # 6) Fix $ref spelling ---------------------------------------------------
    if "ref" in schema and "$ref" not in schema:
        schema["$ref"] = schema.pop("ref").replace("#/$defs", "#/components/schemas")

    return schema


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def PayPalTool(api: PayPalAPI, desc: Dict[str, Any]) -> OpenAPITool:  # noqa: N802
    method_name: str = desc["method"]
    schema_model = desc["args_schema"]
    description: str = desc["description"]

    # 1 / Build OpenAPI 3.0 spec
    print("Before: ", schema_model.model_json_schema())
    request_schema = _json_schema_to_oas3(schema_model.model_json_schema())
    print("After: ",  json.loads(json.dumps(request_schema)))
    openapi_spec: Dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": f"PayPal {method_name}",
            "version": "1.0.0",
            "description": description,
        },
        "servers": [
            {"url": "https://api-m.sandbox.paypal.com"}
        ],
        "paths": {
            f"/{method_name}": {
                "post": {
                    "operationId": method_name,
                    "description": description,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": request_schema}
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Successful PayPal API response",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            }
        },
    }

    # 2 / Build an OpenAPIToolset from the spec then fetch the generated tool
    toolset = OpenAPIToolset(spec_dict=openapi_spec)
    generated_tool: RestApiTool = toolset.get_tool(method_name)
    generated_tool.base_url = "https://api-m.sandbox.paypal.com"

    # Patch the generated tool so that it delegates execution to PayPalAPI
    async def _on_invoke_tool(ctx: ToolContext, **kwargs):  
        print("_on_invoke_tool Called")
        kwargs.pop("tool_context", None)
        return api.run(method_name, kwargs)

    # ADK exposes a public attribute to override the execution callback
    generated_tool.on_invoke_tool = _on_invoke_tool  # type: ignore[attr-defined]


    return generated_tool