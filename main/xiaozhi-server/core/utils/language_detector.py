"""基于大模型的会话语言检测。"""

from __future__ import annotations

import re

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


def _detect_language_by_rules(text: str) -> str:
    """当 LLM 未给出可靠结果时，仅用本地规则兜底识别中英文。"""
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

    if chinese_chars >= 2:
        return "Chinese"
    if latin_chars >= 8 and chinese_chars == 0:
        return "English"
    if chinese_chars >= 1 and latin_chars == 0 and len(signal_text) <= 4:
        return "Chinese"
    if latin_chars >= 3 and chinese_chars == 0 and len(signal_text) <= 8:
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
    """使用主LLM做轻量语言分类。"""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        logger.bind(tag=TAG).debug("语言检测跳过：输入为空，沿用当前会话语言")
        return current_language or "Chinese"

    if _looks_too_short(normalized_text):
        rule_detected = _detect_language_by_rules(normalized_text)
        if rule_detected != "Unknown":
            logger.bind(tag=TAG).info(
                f"语言检测跳过大模型并命中规则: text={normalized_text[:80]!r}, detected={rule_detected}"
            )
            return rule_detected
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
        )
    except TypeError:
        try:
            result = llm.response_no_stream(
                LANGUAGE_DETECT_SYSTEM_PROMPT,
                user_prompt,
            )
        except Exception as exc:
            rule_detected = _detect_language_by_rules(normalized_text)
            if rule_detected != "Unknown":
                logger.bind(tag=TAG).warning(
                    f"语言检测调用失败，已回退规则检测: detected={rule_detected}, error={exc}"
                )
                return rule_detected
            logger.bind(tag=TAG).warning(f"语言检测调用失败，回退当前语言: {exc}")
            return current_language or "Unknown"
    except Exception as exc:
        rule_detected = _detect_language_by_rules(normalized_text)
        if rule_detected != "Unknown":
            logger.bind(tag=TAG).warning(
                f"语言检测调用失败，已回退规则检测: detected={rule_detected}, error={exc}"
            )
            return rule_detected
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
        rule_detected = _detect_language_by_rules(normalized_text)
        if rule_detected != "Unknown":
            logger.bind(tag=TAG).info(
                f"语言检测返回Unknown，已回退规则检测: text={normalized_text[:80]!r}, detected={rule_detected}"
            )
            return rule_detected
        return "Unknown"

    rule_detected = _detect_language_by_rules(normalized_text)
    if rule_detected != "Unknown":
        logger.bind(tag=TAG).warning(
            f"语言检测返回无效值，已回退规则检测: raw={result_text!r}, detected={rule_detected}"
        )
        return rule_detected
    logger.bind(tag=TAG).warning(
        f"语言检测返回无效值，回退当前语言: raw={result_text!r}"
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
