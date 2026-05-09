"""语言配置归一化工具。"""

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
    "阿拉伯语": "Arabic",
    "arabic": "Arabic",
    "ar": "Arabic",
}

PROMPT_LANGUAGE_ALIASES = {
    "Auto": "用户使用的语言",
    "Chinese": "中文",
    "English": "英文",
    "French": "法文",
    "German": "德文",
    "Italian": "意大利文",
    "Japanese": "日文",
    "Korean": "韩文",
    "Portuguese": "葡萄牙文",
    "Russian": "俄文",
    "Spanish": "西班牙文",
    "Arabic": "阿拉伯文",
}


def normalize_tts_language(language, default="Chinese"):
    """将管理端展示值或常见别名转换为上游 TTS 接口枚举。"""
    if language is None:
        return default

    language_text = str(language).strip()
    if not language_text:
        return default

    normalized = TTS_LANGUAGE_ALIASES.get(
        language_text, TTS_LANGUAGE_ALIASES.get(language_text.lower(), language_text)
    )
    return normalized if normalized in SUPPORTED_TTS_LANGUAGES else default


def normalize_prompt_language(language, default="中文"):
    """将 TTS 语言配置转换为适合写入提示词的自然语言描述。"""
    normalized_language = normalize_tts_language(language, default="")
    if not normalized_language:
        return default
    return PROMPT_LANGUAGE_ALIASES.get(normalized_language, normalized_language)


def detect_supported_language(text, default="Chinese"):
    """Best-effort fallback language detection constrained to TTS languages."""
    if not text:
        return default

    text = str(text)
    counters = {
        "Chinese": 0,
        "Japanese": 0,
        "Korean": 0,
        "Russian": 0,
        "Arabic": 0,
    }
    for char in text:
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF:
            counters["Chinese"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counters["Japanese"] += 1
        elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
            counters["Korean"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counters["Russian"] += 1
        elif 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F:
            counters["Arabic"] += 1

    for language in ("Japanese", "Korean", "Russian", "Arabic"):
        if counters[language] > 0:
            return language

    detected, count = max(counters.items(), key=lambda item: item[1])
    if count > 0:
        return detected

    lower = text.lower()
    latin_hints = (
        ("French", ("bonjour", "merci", "français", "francais", "être", "avec", "pour")),
        ("German", ("hallo", "danke", "deutsch", "nicht", "und", "ich", "der", "die")),
        ("Spanish", ("hola", "gracias", "español", "espanol", "usted", "para", "que")),
        ("Portuguese", ("olá", "ola", "obrigado", "português", "portugues", "você", "não")),
        ("Italian", ("ciao", "grazie", "italiano", "perché", "perche", "sono")),
    )
    for language, hints in latin_hints:
        if any(hint in lower for hint in hints):
            return language

    return "English"


def resolve_interaction_language(language_hint=None, text=None, default="Chinese"):
    """Resolve each interaction to exactly one supported TTS language."""
    normalized = normalize_tts_language(language_hint, default="")
    if normalized in SUPPORTED_TTS_LANGUAGES:
        return normalized
    return detect_supported_language(text, default=default)
