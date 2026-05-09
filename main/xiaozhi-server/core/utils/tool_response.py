import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler


_GENERIC_TOOL_PATTERNS = (
    r"\bsearch_from_ragflow\b",
    r"\bRAGFlow\b",
    r"\bRAGflow\b",
    r"\bRAG\b",
    r"\bfunction[_\s-]?call\b",
    r"\btool[_\s-]?call\b",
    r"\bMCP\b",
    r"调用知识库",
    r"查询知识库",
    r"知识库查询结果",
    r"根据知识库查询结果",
    r"调用工具",
    r"工具调用",
)


def _configured_tool_names(conn: "ConnectionHandler") -> list[str]:
    if not hasattr(conn, "func_handler") or conn.func_handler is None:
        return []
    try:
        functions = conn.func_handler.get_functions()
        return [
            item.get("function", {}).get("name")
            for item in functions
            if item.get("function", {}).get("name")
        ]
    except Exception:
        return []


def sanitize_tool_response_for_speech(conn: "ConnectionHandler", text):
    """Remove internal tool or knowledge-base names from user-facing speech."""
    if text is None or not isinstance(text, str):
        return text

    sanitized = text
    for name in _configured_tool_names(conn):
        if name:
            sanitized = re.sub(re.escape(name), "", sanitized, flags=re.IGNORECASE)

    for pattern in _GENERIC_TOOL_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    replacements = {
        "根据查询结果，": "",
        "根据查询结果": "",
        "根据结果，": "",
        "根据结果": "",
        "我查到": "查询到",
        "我帮你查到": "查询到",
    }
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)

    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = re.sub(r"^[，,。:：；;\s]+", "", sanitized)
    return sanitized.strip()


def wrap_tool_result_for_llm(tool_name: str, result_text, language: str = None):
    """Add a non-spoken instruction around tool output before asking the LLM."""
    if result_text is None or not isinstance(result_text, str):
        return result_text
    language_instruction = (
        f"最终面向用户的回答必须使用 {language}。" if language else ""
    )
    return (
        "以下是内部工具返回的信息，仅用于组织最终回答。"
        "最终回答必须直接回答用户，不要说出或展示工具名、函数名、知识库名，"
        "也不要说“调用工具”“查询知识库”“根据知识库”等过程说明。"
        f"{language_instruction}\n\n"
        f"<internal_tool_name>{tool_name}</internal_tool_name>\n"
        f"<tool_result>\n{result_text}\n</tool_result>"
    )
