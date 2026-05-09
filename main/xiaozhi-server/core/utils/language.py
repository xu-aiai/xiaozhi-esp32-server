"""语言配置归一化工具。"""

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
