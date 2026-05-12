import unittest
from collections import deque
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

from core.utils.language_detector import update_session_language
from core.utils.prompt_manager import PromptManager


class UpdateSessionLanguageTest(unittest.TestCase):
    def test_short_english_phrase_switches_session_language(self):
        conn = SimpleNamespace(
            current_language="Chinese", language_detect_history=deque(maxlen=3)
        )

        result = update_session_language(conn, "English", "hi maia")

        self.assertEqual(result, "English")

    def test_single_latin_word_does_not_switch_language(self):
        conn = SimpleNamespace(
            current_language="Chinese", language_detect_history=deque(maxlen=3)
        )

        result = update_session_language(conn, "English", "hello")

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


if __name__ == "__main__":
    unittest.main()
