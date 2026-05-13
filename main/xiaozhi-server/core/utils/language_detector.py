"""基于本地规则的会话语言检测。"""

from __future__ import annotations

import re

from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

SUPPORTED_TTS_LANGUAGES = {
    "Chinese",
    "English",
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


def _detect_language_by_rules(text: str) -> str:
    """仅用本地规则识别中英文。"""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return "Unknown"

    signal_text = re.sub(
        r"[\s`*_#>\-\[\](){},.:;!?~，。！？；：、】【…]+", "", normalized_text
    )
    if not signal_text:
        return "Unknown"

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", signal_text))
    latin_chars = len(re.findall(r"[A-Za-z]", signal_text))
    total_chars = len(signal_text)

    if chinese_chars == 0 and latin_chars == 0:
        return "Unknown"

    if chinese_chars >= 2:
        return "Chinese"
    if latin_chars >= 8 and chinese_chars == 0:
        return "English"
    if chinese_chars >= 1 and latin_chars == 0 and len(signal_text) <= 4:
        return "Chinese"
    if latin_chars >= 3 and chinese_chars == 0 and len(signal_text) <= 8:
        return "English"
    if chinese_chars > latin_chars and chinese_chars >= 2:
        return "Chinese"
    if latin_chars > chinese_chars and latin_chars >= 5:
        return "English"
    if total_chars > 0 and chinese_chars / total_chars >= 0.4:
        return "Chinese"
    if total_chars > 0 and latin_chars / total_chars >= 0.6:
        return "English"
    return "Unknown"


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
    """兼容旧接口名，实际改为本地规则检测，仅支持中英文。"""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        logger.bind(tag=TAG).debug("规则检测跳过：输入为空，沿用当前会话语言")
        return current_language or "Chinese"

    logger.bind(tag=TAG).info(
        f"开始规则语言检测: current={current_language or 'None'}, text={normalized_text[:120]!r}"
    )
    if _looks_too_short(normalized_text):
        detected = _detect_language_by_rules(normalized_text)
        if detected != "Unknown":
            logger.bind(tag=TAG).info(
                f"短文本规则检测命中: text={normalized_text[:80]!r}, detected={detected}"
            )
            return detected
        logger.bind(tag=TAG).debug(
            f"短文本规则检测未命中，沿用当前语言: text={normalized_text[:80]!r}, current={current_language or 'None'}"
        )
        return current_language or "Unknown"

    detected = _detect_language_by_rules(normalized_text)
    if detected != "Unknown":
        logger.bind(tag=TAG).info(
            f"规则语言检测成功: text={normalized_text[:80]!r}, detected={detected}"
        )
        return detected

    logger.bind(tag=TAG).info(
        f"规则语言检测未命中: text={normalized_text[:80]!r}, current={current_language or 'None'}"
    )
    return current_language or "Unknown"


def update_session_language(conn, detected_language: str, text: str) -> str:
    """根据语言检测结果更新会话语言。"""
    current_language = getattr(conn, "current_language", None) or "Chinese"
    normalized_text = _normalize_text(text)

    if detected_language == "Unknown":
        logger.bind(tag=TAG).info(
            f"语言检测结果为Unknown，沿用当前会话语言: current={current_language}, text={normalized_text[:80]!r}"
        )
        return current_language

    if current_language == detected_language:
        logger.bind(tag=TAG).info(
            f"语言检测结果与当前会话语言一致: current={current_language}, text={normalized_text[:80]!r}"
        )
        return current_language

    logger.bind(tag=TAG).info(
        f"切换会话语言: {current_language} -> {detected_language}, text={normalized_text[:80]!r}"
    )
    return detected_language
