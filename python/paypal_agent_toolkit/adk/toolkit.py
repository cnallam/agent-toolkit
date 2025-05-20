"""
Google ADK  PayPal Toolkit built on ``PayPalTool``.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import PrivateAttr

# from google.adk.tools.openapi_tool.openapi_spec_parser.rest_api_tool import RestApiTool

from ..shared.api import PayPalAPI
from ..shared.configuration import Configuration, is_tool_allowed
from ..shared.tools import tools  
from .tool import PayPalTool  
from google.adk.tools import FunctionTool, ToolContext  



class PayPalToolkit:
    """PayPal Toolkit for Google ADK."""

    _tools: List[FunctionTool] = PrivateAttr()
    SOURCE = "ADK"

    # ------------------------------------------------------------------
    def __init__(
        self,
        client_id: str,
        secret: str,
        configuration: Optional[Configuration] = None,
    ) -> None:
        self._tools = []

        self.configuration = configuration or Configuration()
        self.context = (
            self.configuration.context
            if self.configuration and self.configuration.context
            else Configuration.Context.default()
        )
        self.context.source = self.SOURCE

        paypal_api = PayPalAPI(client_id=client_id, secret=secret, context=self.context)

        filtered_tools = [t for t in tools if is_tool_allowed(t, self.configuration)]

        for tool in filtered_tools:
            self._tools.append(PayPalTool(paypal_api, tool))


    def get_tools(self) -> List[FunctionTool]:
        """Return the list of enabled PayPal FunctionTools."""
        return self._tools