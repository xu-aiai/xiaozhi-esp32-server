"""语言配置归一化工具。"""

from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

_SUPPORTED_LANGUAGES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
}

PLUGIN_LANGUAGE_CODE_MAP = {
    "Chinese": "zh_CN",
    "English": "en_US",
    "Japanese": "ja_JP",
    "Korean": "ko_KR",
    "French": "fr_FR",
    "German": "de_DE",
    "Russian": "ru_RU",
    "Portuguese": "pt_PT",
    "Spanish": "es_ES",
    "Italian": "it_IT",
    "Arabic": "ar_SA",
}

QWEATHER_LANGUAGE_CODE_MAP = {
    "zh_CN": "zh",
    "zh_HK": "zh-hk",
    "en_US": "en",
    "ja_JP": "ja",
    "ko_KR": "ko",
    "fr_FR": "fr",
    "de_DE": "de",
    "ru_RU": "ru",
    "pt_PT": "pt",
    "pt_BR": "pt",
    "es_ES": "es",
    "it_IT": "it",
    "ar_SA": "ar",
}

TTS_LANGUAGE_ALIASES = {
    "auto": "Auto",
    "automatic": "Auto",
    "multilingual": "Auto",
    "multi-language": "Auto",
    "multi_language": "Auto",
    "多语言": "Auto",
    "自动": "Auto",
    "自动检测": "Auto",
    "中文": "Chinese",
    "汉语": "Chinese",
    "普通话": "Chinese",
    "chinese": "Chinese",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "zh_cn": "Chinese",
    "英语": "English",
    "英文": "English",
    "english": "English",
    "en": "English",
    "法语": "French",
    "french": "French",
    "fr": "French",
    "德语": "German",
    "german": "German",
    "de": "German",
    "意大利语": "Italian",
    "italian": "Italian",
    "it": "Italian",
    "阿拉伯语": "Arabic",
    "arabic": "Arabic",
    "ar": "Arabic",
    "日语": "Japanese",
    "日文": "Japanese",
    "japanese": "Japanese",
    "ja": "Japanese",
    "韩语": "Korean",
    "韩文": "Korean",
    "korean": "Korean",
    "ko": "Korean",
    "葡萄牙语": "Portuguese",
    "portuguese": "Portuguese",
    "pt": "Portuguese",
    "俄语": "Russian",
    "russian": "Russian",
    "ru": "Russian",
    "西班牙语": "Spanish",
    "spanish": "Spanish",
    "es": "Spanish",
}

PROMPT_LANGUAGE_ALIASES = {
    "Auto": "用户使用的语言",
    "Chinese": "中文",
    "English": "英文",
    "French": "法文",
    "German": "德文",
    "Italian": "意大利文",
    "Arabic": "阿拉伯文",
    "Japanese": "日文",
    "Korean": "韩文",
    "Portuguese": "葡萄牙文",
    "Russian": "俄文",
    "Spanish": "西班牙文",
}

DISPLAY_TEXT_I18N = {
    "processing": {
        "Chinese": "正在处理",
        "English": "Processing",
        "Japanese": "処理中",
        "Korean": "처리 중",
        "French": "Traitement en cours",
        "German": "Wird verarbeitet",
        "Russian": "Обработка",
        "Portuguese": "Processando",
        "Spanish": "Procesando",
        "Italian": "Elaborazione in corso",
        "Arabic": "جارٍ المعالجة",
    }
}

END_PROMPT_I18N = {
    "Chinese": '请你以"时间过得真快"为开头，用富有感情、依依不舍的话来结束这场对话吧！',
    "English": 'Please begin with "Time flies so fast" and end this conversation in a warm, emotional, and reluctant-to-say-goodbye tone.',
}


def normalize_tts_language(language, default="Chinese"):
    """将管理端展示值或常见别名转换为上游 TTS 接口枚举。"""
    if language is None:
        return default

    language_text = str(language).strip()
    if not language_text:
        return default

    return TTS_LANGUAGE_ALIASES.get(
        language_text, TTS_LANGUAGE_ALIASES.get(language_text.lower(), language_text)
    )


def normalize_prompt_language(language, default="中文"):
    """将 TTS 语言配置转换为适合写入提示词的自然语言描述。"""
    normalized_language = normalize_tts_language(language, default="")
    if not normalized_language:
        return default
    return PROMPT_LANGUAGE_ALIASES.get(normalized_language, normalized_language)


def get_session_tts_language(conn, fallback=None):
    """优先读取当前会话语言，其次回退到配置值。"""
    session_language = getattr(conn, "current_language", None) if conn else None
    resolved = normalize_tts_language(
        session_language if session_language else fallback,
        default="Chinese",
    )
    if resolved == "Auto":
        logger.bind(tag=TAG).warning(
            "TTS language 解析结果为 Auto，已回退为 Chinese"
        )
        return "Chinese"
    return resolved


def get_plugin_language_code(language, default="zh_CN"):
    """将会话语言或别名转换为插件使用的 locale code。"""
    normalized = normalize_tts_language(language, default="")
    if not normalized:
        return default
    return PLUGIN_LANGUAGE_CODE_MAP.get(normalized, default)


def get_conn_plugin_language(conn, default="zh_CN"):
    """从连接对象读取当前插件语言码。"""
    session_language = getattr(conn, "current_language", None) if conn else None
    return get_plugin_language_code(session_language, default=default)


def get_qweather_language_code(language_code, default="zh"):
    """将插件语言码转换为和风天气语言码。"""
    if language_code is None:
        return default
    code = str(language_code).strip()
    if not code:
        return default
    return QWEATHER_LANGUAGE_CODE_MAP.get(code, default)


def get_supported_downstream_language(language, default="zh-CN"):
    """将当前会话语言收口为下游仅支持的 language 值。"""
    normalized = normalize_tts_language(language, default="")
    if normalized == "English":
        key = "en"
    else:
        key = "zh"
    return _SUPPORTED_LANGUAGES.get(key, default)


def get_conn_downstream_language(conn, default="zh-CN"):
    """从连接对象读取当前会话语言，并映射为下游受支持的 language。"""
    session_language = getattr(conn, "current_language", None) if conn else None
    return get_supported_downstream_language(session_language, default=default)


def get_display_text(key: str, language, default="正在处理"):
    """将固定展示文案按当前会话语言做国际化映射。"""
    translations = DISPLAY_TEXT_I18N.get(key, {})
    if not translations:
        return default

    normalized = normalize_tts_language(language, default="Chinese")
    return translations.get(normalized, translations.get("Chinese", default))


def get_conn_display_text(conn, key: str, default="正在处理"):
    """从连接对象读取当前会话语言，并返回对应的国际化展示文案。"""
    session_language = getattr(conn, "current_language", None) if conn else None
    return get_display_text(key, session_language, default=default)


def get_end_prompt_text(language, configured_prompt=None):
    """按当前会话语言返回结束提示词。"""
    normalized = normalize_tts_language(language, default="Chinese")

    if isinstance(configured_prompt, dict):
        localized = (
            configured_prompt.get(normalized)
            or configured_prompt.get("default")
            or configured_prompt.get("Chinese")
        )
        if localized:
            return str(localized).strip()

    configured_text = str(configured_prompt).strip() if configured_prompt else ""
    if normalized == "Chinese" and configured_text:
        return configured_text

    return END_PROMPT_I18N.get(normalized, END_PROMPT_I18N["Chinese"])
