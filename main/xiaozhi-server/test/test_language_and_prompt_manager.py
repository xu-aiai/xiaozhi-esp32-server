import unittest
from types import SimpleNamespace
import sys
import types


fake_config = types.ModuleType("config")
fake_logger_module = types.ModuleType("config.logger")


class _FakeLogger:
    def bind(self, **kwargs):
        return self

    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


fake_logger_module.setup_logging = lambda: _FakeLogger()
fake_jinja2 = types.ModuleType("jinja2")
fake_jinja2.Template = object
sys.modules.setdefault("config", fake_config)
sys.modules["config.logger"] = fake_logger_module
sys.modules["jinja2"] = fake_jinja2

from core.utils.language_detector import detect_language_with_llm, update_session_language
from core.utils.language import get_display_text, get_end_prompt_text
from core.utils.prompt_manager import PromptManager
from core.utils.textUtils import strip_markdown_for_display


class UpdateSessionLanguageTest(unittest.TestCase):
    def test_detected_language_is_applied_directly(self):
        conn = SimpleNamespace(current_language="Chinese")

        result = update_session_language(conn, "English", "hi maia")

        self.assertEqual(result, "English")

    def test_short_text_detected_as_english_still_switches_language(self):
        conn = SimpleNamespace(current_language="Chinese")

        result = update_session_language(conn, "English", "hello")

        self.assertEqual(result, "English")

    def test_unknown_keeps_current_language(self):
        conn = SimpleNamespace(current_language="English")

        result = update_session_language(conn, "Unknown", "ok")

        self.assertEqual(result, "English")


class RuleLanguageDetectorTest(unittest.TestCase):
    def test_detects_chinese_by_rules(self):
        result = detect_language_with_llm(None, "今天天气不错", "English")

        self.assertEqual(result, "Chinese")

    def test_detects_english_by_rules(self):
        result = detect_language_with_llm(None, "please play some music", "Chinese")

        self.assertEqual(result, "English")

    def test_unknown_text_keeps_current_language(self):
        result = detect_language_with_llm(None, "123456", "Chinese")

        self.assertEqual(result, "Chinese")


class PromptManagerWeatherPrefetchTest(unittest.TestCase):
    def test_skip_weather_prefetch_when_plugin_not_configured(self):
        manager = PromptManager.__new__(PromptManager)
        manager.logger = _FakeLogger()
        manager.cache_manager = SimpleNamespace(get=lambda *args, **kwargs: None)
        manager.CacheType = SimpleNamespace(WEATHER="WEATHER")

        conn = SimpleNamespace(config={"plugins": {}})

        result = manager._get_weather_info(conn, "上海")

        self.assertEqual(result, "")


class TextUtilsTest(unittest.TestCase):
    def test_strip_markdown_for_display(self):
        text = "**你好**，请看[这里](https://example.com) 和 `code`"

        result = strip_markdown_for_display(text)

        self.assertEqual(result, "你好，请看这里 和 code")


class LanguageDisplayTextTest(unittest.TestCase):
    def test_processing_display_text_in_english(self):
        result = get_display_text("processing", "English")

        self.assertEqual(result, "Processing")

    def test_processing_display_text_falls_back_to_chinese(self):
        result = get_display_text("processing", "UnknownLanguage")

        self.assertEqual(result, "正在处理")


class EndPromptTextTest(unittest.TestCase):
    def test_end_prompt_uses_configured_chinese_text(self):
        result = get_end_prompt_text("Chinese", "这是自定义中文结束提示")

        self.assertEqual(result, "这是自定义中文结束提示")

    def test_end_prompt_uses_english_i18n_text(self):
        result = get_end_prompt_text("English", "这是自定义中文结束提示")

        self.assertIn("Time flies so fast", result)


if __name__ == "__main__":
    unittest.main()
