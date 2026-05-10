"""基于大模型的会话语言检测。"""

from __future__ import annotations

import re
from collections import deque

from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

SUPPORTED_TTS_LANGUAGES = {
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian",
    "Arabic",
}

SHORT_CONFIRMATION_WORDS = {
    "ok",
    "okay",
    "yes",
    "no",
    "hi",
    "hello",
    "bye",
    "thanks",
    "thank you",
}

LANGUAGE_DETECT_SYSTEM_PROMPT = """你是语言识别器。
任务：根据用户文本判断最适合用于回复和TTS播报的语言。
只允许输出以下枚举之一：
Chinese
English
Japanese
Korean
French
German
Russian
Portuguese
Spanish
Italian
Arabic
Unknown

规则：
1. 只输出一个词，不要解释。
2. 如果文本很短且无法可靠判断，输出 Unknown。
3. 如果是混合语言，输出用户本轮主要语言。
4. 应判断“最适合回复用户的语言”，而不是只看个别外文单词。
5. 品牌名、人名、歌曲名、技术词汇不能单独决定语言。
"""


def _normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    return str(text).strip()


def _looks_too_short(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return True
    if len(compact) <= 3:
        return True
    if compact.lower() in SHORT_CONFIRMATION_WORDS:
        return True
    return False


def _normalize_detected_language(language: str | None) -> str | None:
    if not language:
        return None
    value = str(language).strip()
    if not value:
        return None
    if value == "Unknown":
        return "Unknown"
    canonical = value[:1].upper() + value[1:].lower()
    if canonical in SUPPORTED_TTS_LANGUAGES:
        return canonical
    return None


def detect_language_with_llm(llm, text: str, current_language: str | None = None) -> str:
    """使用主LLM做轻量语言分类。"""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        logger.bind(tag=TAG).debug("语言检测跳过：输入为空，沿用当前会话语言")
        return current_language or "Chinese"

    if _looks_too_short(normalized_text):
        logger.bind(tag=TAG).debug(
            f"语言检测跳过：输入过短，text={normalized_text[:80]!r}, current={current_language or 'None'}"
        )
        return current_language or "Unknown"

    logger.bind(tag=TAG).info(
        f"开始语言检测: current={current_language or 'None'}, text={normalized_text[:120]!r}"
    )

    user_prompt = (
        f"当前会话语言：{current_language or 'None'}\n"
        f"用户文本：{normalized_text}\n"
        "请输出语言枚举："
    )

    try:
        result = llm.response_no_stream(
            LANGUAGE_DETECT_SYSTEM_PROMPT,
            user_prompt,
            temperature=0,
            max_tokens=8,
            top_p=0.1,
        )
    except TypeError:
        try:
            result = llm.response_no_stream(
                LANGUAGE_DETECT_SYSTEM_PROMPT,
                user_prompt,
            )
        except Exception as exc:
            logger.bind(tag=TAG).warning(f"语言检测调用失败，回退当前语言: {exc}")
            return current_language or "Unknown"
    except Exception as exc:
        logger.bind(tag=TAG).warning(f"语言检测调用失败，回退当前语言: {exc}")
        return current_language or "Unknown"

    detected = _normalize_detected_language(result)
    if detected:
        logger.bind(tag=TAG).info(
            f"语言检测成功: text={normalized_text[:80]!r}, raw={str(result).strip()!r}, detected={detected}"
        )
        return detected

    result_text = _normalize_text(result)
    if result_text == "Unknown":
        return "Unknown"

    logger.bind(tag=TAG).warning(
        f"语言检测返回无效值，回退当前语言: raw={result_text!r}"
    )
    return current_language or "Unknown"


def update_session_language(conn, detected_language: str, text: str) -> str:
    """结合短句保护和简单平滑策略，更新会话语言。"""
    current_language = getattr(conn, "current_language", None) or "Chinese"
    normalized_text = _normalize_text(text)

    if not hasattr(conn, "language_detect_history") or conn.language_detect_history is None:
        conn.language_detect_history = deque(maxlen=3)

    if detected_language == "Unknown":
        logger.bind(tag=TAG).info(
            f"语言检测结果为Unknown，沿用当前会话语言: current={current_language}, text={normalized_text[:80]!r}"
        )
        return current_language

    if _looks_too_short(normalized_text):
        logger.bind(tag=TAG).info(
            f"输入过短，不触发语言切换: current={current_language}, detected={detected_language}, text={normalized_text[:80]!r}"
        )
        return current_language

    if current_language == detected_language:
        conn.language_detect_history.clear()
        logger.bind(tag=TAG).info(
            f"语言检测结果与当前会话语言一致: current={current_language}, text={normalized_text[:80]!r}"
        )
        return current_language

    conn.language_detect_history.append(detected_language)
    should_switch = False

    if len(normalized_text) >= 8:
        should_switch = True

    if len(conn.language_detect_history) >= 2:
        recent = list(conn.language_detect_history)[-2:]
        if recent[0] == recent[1] == detected_language:
            should_switch = True

    if should_switch:
        logger.bind(tag=TAG).info(
            f"切换会话语言: {current_language} -> {detected_language}, text={normalized_text[:80]!r}"
        )
        conn.language_detect_history.clear()
        return detected_language

    logger.bind(tag=TAG).debug(
        f"暂不切换会话语言: current={current_language}, detected={detected_language}, history={list(conn.language_detect_history)}, text={normalized_text[:80]!r}"
    )
    return current_language
