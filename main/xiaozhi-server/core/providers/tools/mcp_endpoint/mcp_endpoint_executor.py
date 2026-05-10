"""MCP接入点工具执行器"""

from typing import Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from plugins_func.register import Action, ActionResponse
from .mcp_endpoint_handler import call_mcp_endpoint_tool


class MCPEndpointExecutor(ToolExecutor):
    """MCP接入点工具执行器"""

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _extract_business_error(result_json: Dict[str, Any]) -> str | None:
        """识别MCP工具业务错误，避免把参数错误交给LLM反复自修。"""
        if not isinstance(result_json, dict):
            return None

        if result_json.get("success") is False:
            return str(result_json.get("msg") or result_json.get("message") or "工具返回失败")

        data = result_json.get("data")
        if isinstance(data, dict):
            code = data.get("code")
            if code not in (None, 0, "0"):
                return str(data.get("msg") or data.get("message") or "工具返回业务错误")

        return None

    async def execute(
        self, conn, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行MCP接入点工具"""
        if not hasattr(conn, "mcp_endpoint_client") or not conn.mcp_endpoint_client:
            return ActionResponse(
                action=Action.ERROR,
                response="MCP接入点客户端未初始化",
            )

        if not await conn.mcp_endpoint_client.is_ready():
            return ActionResponse(
                action=Action.ERROR,
                response="MCP接入点客户端未准备就绪",
            )

        try:
            # 转换参数为JSON字符串
            import json

            args_str = json.dumps(arguments) if arguments else "{}"

            # 调用MCP接入点工具
            result = await call_mcp_endpoint_tool(
                conn.mcp_endpoint_client, tool_name, args_str
            )

            resultJson = None
            if isinstance(result, str):
                try:
                    resultJson = json.loads(result)
                except Exception as e:
                    pass

            if resultJson is not None:
                business_error = self._extract_business_error(resultJson)
                if business_error:
                    return ActionResponse(
                        action=Action.ERROR,
                        response=business_error,
                    )

            # 本地 Action 只处理内部约定的枚举值。
            # MCP 业务动作（如 select_device / ask_missing_info）统一交给 LLM 续写，
            # 以便把 message/state 组织成自然语言回复，并保留会话上下文。
            if (
                resultJson is not None
                and isinstance(resultJson, dict)
                and "action" in resultJson
            ):
                action_name = str(resultJson.get("action", "")).upper()
                if action_name in Action.__members__:
                    return ActionResponse(
                        action=Action[action_name],
                        response=(
                            resultJson.get("response")
                            or resultJson.get("message", "")
                        ),
                    )

                return ActionResponse(
                    action=Action.REQLLM,
                    result=result,
                )

            return ActionResponse(action=Action.REQLLM, result=str(result))

        except ValueError as e:
            return ActionResponse(action=Action.NOTFOUND, response=str(e))
        except Exception as e:
            return ActionResponse(action=Action.ERROR, response=str(e))

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取所有MCP接入点工具"""
        if (
            not hasattr(self.conn, "mcp_endpoint_client")
            or not self.conn.mcp_endpoint_client
        ):
            return {}

        tools = {}
        mcp_tools = self.conn.mcp_endpoint_client.get_available_tools()

        for tool in mcp_tools:
            func_def = tool.get("function", {})
            tool_name = func_def.get("name", "")

            if tool_name:
                tools[tool_name] = ToolDefinition(
                    name=tool_name, description=tool, tool_type=ToolType.MCP_ENDPOINT
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定的MCP接入点工具"""
        if (
            not hasattr(self.conn, "mcp_endpoint_client")
            or not self.conn.mcp_endpoint_client
        ):
            return False

        return self.conn.mcp_endpoint_client.has_tool(tool_name)
