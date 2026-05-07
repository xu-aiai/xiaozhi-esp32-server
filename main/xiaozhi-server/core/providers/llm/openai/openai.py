import json
import httpx
import openai
from openai.types import CompletionUsage
from config.logger import setup_logging
from core.utils.util import check_model_key
from core.providers.llm.base import LLMProviderBase
from urllib.parse import urlparse

TAG = __name__
logger = setup_logging()

# 需要禁用思考模式的平台域名及其对应参数（默认关闭思考模式）
THINKING_DISABLED_DOMAINS = {
    "aliyuncs.com": {"enable_thinking": False},
    "bigmodel.cn": {"thinking": {"type": "disabled"}},
    "moonshot.cn": {"thinking": {"type": "disabled"}},
    "volces.com": {"thinking": {"type": "disabled"}},
}

MERGE_SYSTEM_MESSAGE_MODELS = {
    "Qwen3.6-35B-A3.5B",
    "Qwen3.6-35B-A3B",
}

MINIMAX_REASONING_SPLIT_MODEL_PREFIXES = (
    "minimax-m2",
)


class ThinkContentFilter:
    """流式过滤 <think>...</think>，可处理标签被拆到多个 chunk 的情况。"""

    START_TAG = "<think>"
    END_TAG = "</think>"
    MAX_TAG_LEN = max(len(START_TAG), len(END_TAG))

    def __init__(self):
        self.in_think = False
        self.pending = ""

    def feed(self, content):
        if not content:
            return content

        text = self.pending + content
        self.pending = ""
        output = []

        while text:
            if self.in_think:
                end_index = text.find(self.END_TAG)
                if end_index == -1:
                    self.pending = self._extract_possible_tag_tail(text)
                    return ""
                text = text[end_index + len(self.END_TAG):]
                self.in_think = False
                continue

            start_index = text.find(self.START_TAG)
            if start_index == -1:
                tail = self._extract_possible_tag_tail(text)
                if tail:
                    output.append(text[:-len(tail)])
                    self.pending = tail
                else:
                    output.append(text)
                return "".join(output)

            output.append(text[:start_index])
            text = text[start_index + len(self.START_TAG):]
            self.in_think = True

        return "".join(output)

    def flush(self):
        if self.in_think:
            self.pending = ""
            self.in_think = False
            return ""
        content = self.pending
        self.pending = ""
        return content

    def _extract_possible_tag_tail(self, text):
        max_tail_len = min(len(text), self.MAX_TAG_LEN - 1)
        for tail_len in range(max_tail_len, 0, -1):
            tail = text[-tail_len:]
            if self.START_TAG.startswith(tail) or self.END_TAG.startswith(tail):
                return tail
        return ""


def _to_loggable(value):
    """Convert OpenAI SDK objects to JSON-serializable data for debug logs."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _to_loggable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_loggable(v) for v in value]
    if isinstance(value, tuple):
        return [_to_loggable(v) for v in value]
    return value


def _log_json(label, payload):
    logger.bind(tag=TAG).debug(
        f"{label}: {json.dumps(_to_loggable(payload), ensure_ascii=False, default=str)}"
    )


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.api_key = config.get("api_key")
        if "base_url" in config:
            self.base_url = config.get("base_url")
        else:
            self.base_url = config.get("url")
        
        timeout_config = config.get("timeout")
        if isinstance(timeout_config, dict):
            # 细粒度超时配置
            custom_timeout = httpx.Timeout(
                pool=timeout_config.get("pool", 2.0),
                connect=timeout_config.get("connect", 3.0),
                write=timeout_config.get("write", 5.0),
                read=timeout_config.get("read", 60.0)
            )
        elif isinstance(timeout_config, (int, float)) and timeout_config > 0:
            # 兼容旧的单一超时配置（整数或浮点数）
            custom_timeout = httpx.Timeout(timeout_config)
        else:
            # 未配置或配置无效，使用默认值
            custom_timeout = httpx.Timeout(300)

        param_defaults = {
            "max_tokens": int,
            "temperature": lambda x: round(float(x), 1),
            "top_p": lambda x: round(float(x), 1),
            "frequency_penalty": lambda x: round(float(x), 1),
        }

        for param, converter in param_defaults.items():
            value = config.get(param)
            try:
                setattr(
                    self,
                    param,
                    converter(value) if value not in (None, "") else None,
                )
            except (ValueError, TypeError):
                setattr(self, param, None)

        logger.debug(
            f"意图识别参数初始化: {self.temperature}, {self.max_tokens}, {self.top_p}, {self.frequency_penalty}"
        )

        model_key_msg = check_model_key("LLM", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=custom_timeout)

    @staticmethod
    def normalize_dialogue(dialogue):
        """自动修复 dialogue 中缺失 content 的消息"""
        for msg in dialogue:
            if "role" in msg and "content" not in msg:
                msg["content"] = ""
        return dialogue

    def _merge_system_messages_if_needed(self, dialogue):
        """部分 OpenAI 兼容模型只接受单条 system，将 system 内容合并到第一条。"""
        if self.model_name not in MERGE_SYSTEM_MESSAGE_MODELS:
            return dialogue

        system_messages = [msg for msg in dialogue if msg.get("role") == "system"]
        if len(system_messages) <= 1:
            return dialogue

        non_system_messages = [msg for msg in dialogue if msg.get("role") != "system"]
        merged_system_message = dict(system_messages[0])
        merged_system_message["content"] = "\n\n".join(
            str(msg.get("content", "")) for msg in system_messages
        )

        logger.bind(tag=TAG).debug(
            f"模型 {self.model_name} 已合并 {len(system_messages)} 条 system 消息"
        )
        return [merged_system_message] + non_system_messages

    def _apply_thinking_disabled(self, request_params: dict):
        """根据域名自动禁用思考模式"""
        parsed_url = urlparse(self.base_url)
        domain = parsed_url.netloc
        for disabled_domain, params in THINKING_DISABLED_DOMAINS.items():
            if disabled_domain in domain:
                request_params.setdefault("extra_body", {}).update(params)
                logger.bind(tag=TAG).info(f"为域名 {domain} 禁用思考模式，参数: {params}")
                break

    def _apply_minimax_reasoning_split(self, request_params: dict):
        """MiniMax M2 系列支持将思考内容拆到 reasoning_details，避免混入 content。"""
        model_name = (self.model_name or "").lower()
        if not model_name.startswith(MINIMAX_REASONING_SPLIT_MODEL_PREFIXES):
            return

        request_params.setdefault("extra_body", {})["reasoning_split"] = True
        logger.bind(tag=TAG).info(
            f"为模型 {self.model_name} 启用 reasoning_split，避免思考内容进入 content"
        )

    def response(self, session_id, dialogue, **kwargs):
        dialogue = self.normalize_dialogue(dialogue)
        dialogue = self._merge_system_messages_if_needed(dialogue)

        request_params = {
            "model": self.model_name,
            "messages": dialogue,
            "stream": True,
        }

        # 添加可选参数,只有当参数不为None时才添加
        optional_params = {
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
        }

        for key, value in optional_params.items():
            if value is not None:
                request_params[key] = value

        # 禁用思考模式
        self._apply_thinking_disabled(request_params)
        self._apply_minimax_reasoning_split(request_params)
        _log_json("OpenAI LLM完整输入参数", request_params)

        responses = self.client.chat.completions.create(**request_params)

        think_filter = ThinkContentFilter()
        try:            
            for chunk in responses:
                _log_json("OpenAI LLM完整原始输出chunk", chunk)
                try:
                    delta = chunk.choices[0].delta if getattr(chunk, "choices", None) else None
                    content = getattr(delta, "content", "") if delta else ""
                except IndexError:
                    content = ""
                if content:
                    filtered_content = think_filter.feed(content)
                    if filtered_content:
                        yield filtered_content
            filtered_content = think_filter.flush()
            if filtered_content:
                yield filtered_content
        finally:
            responses.close()

    def response_with_functions(self, session_id, dialogue, functions=None, **kwargs):
        dialogue = self.normalize_dialogue(dialogue)
        dialogue = self._merge_system_messages_if_needed(dialogue)

        request_params = {
            "model": self.model_name,
            "messages": dialogue,
            "stream": True,
            "tools": functions,
        }

        optional_params = {
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
        }

        for key, value in optional_params.items():
            if value is not None:
                request_params[key] = value

        # 禁用思考模式
        self._apply_thinking_disabled(request_params)
        self._apply_minimax_reasoning_split(request_params)
        _log_json("OpenAI LLM完整输入参数", request_params)

        stream = self.client.chat.completions.create(**request_params)

        think_filter = ThinkContentFilter()
        try:
            for chunk in stream:
                _log_json("OpenAI LLM完整原始输出chunk", chunk)
                if getattr(chunk, "choices", None):
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", "")
                    tool_calls = getattr(delta, "tool_calls", None)
                    filtered_content = think_filter.feed(content)
                    yield filtered_content, tool_calls
                elif isinstance(getattr(chunk, "usage", None), CompletionUsage):
                    usage_info = getattr(chunk, "usage", None)
                    logger.bind(tag=TAG).info(
                        f"Token 消耗：输入 {getattr(usage_info, 'prompt_tokens', '未知')}，"
                        f"输出 {getattr(usage_info, 'completion_tokens', '未知')}，"
                        f"共计 {getattr(usage_info, 'total_tokens', '未知')}"
                    )
            filtered_content = think_filter.flush()
            if filtered_content:
                yield filtered_content, None
        finally:
            stream.close()
