import requests

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase
from core.utils.language import get_session_tts_language, normalize_tts_language
from core.utils.util import check_model_key

TAG = __name__
logger = setup_logging()

FLAT_TONE_INSTRUCTIONS = "强制语气平缓，不带情绪。禁止抑扬顿挫。"


class TTSProvider(TTSProviderBase):
    TTS_PARAM_CONFIG = [
        ("ttsRate", "speed", 0.25, 4, 1, lambda v: round(float(v), 2)),
    ]

    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_key = (config.get("api_key") or "").strip()
        self.api_url = config.get(
            "api_url", "http://10.90.252.47:8091/v1/audio/speech"
        )
        self.model = (config.get("model") or "").strip()
        self.voice = config.get("private_voice") or config.get("voice", "vivian")
        self.language = normalize_tts_language(config.get("language"), "Chinese")
        self.task_type = config.get("task_type", "CustomVoice")
        self.instructions = config.get("instructions", "")
        self.audio_file_type = config.get("format", "wav")
        self.output_file = config.get("output_dir", "tmp/")
        self.timeout = float(config.get("timeout", 300))
        self.extra = config.get("extra", {}) or {}

        speed = config.get("speed", "1.0")
        self.speed = float(speed) if speed not in (None, "") else 1.0
        self._apply_percentage_params(config)

        model_key_msg = check_model_key("TTS", self.api_key)
        if model_key_msg and self.api_key:
            logger.bind(tag=TAG).error(model_key_msg)
        logger.bind(tag=TAG).info(
            "初始化上游TTS: "
            f"url={self.api_url}, model={'<empty>' if not self.model else self.model}, "
            f"voice={self.voice}, language={self.language}, task_type={self.task_type}, "
            f"format={self.audio_file_type}, speed={self.speed}, timeout={self.timeout}s, "
            f"api_key={'set' if self.api_key else 'empty'}"
        )

    async def text_to_speak(self, text, output_file):
        current_language = get_session_tts_language(self.conn, self.language)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = {
            "input": text,
            "voice": self.voice,
            "language": current_language,
            "response_format": self.audio_file_type,
            "task_type": self.task_type,
            "stream": False,
            "instructions": self.instructions,
            "speed": self.speed,
        }
        if self.model:
            data["model"] = self.model
        if isinstance(self.extra, dict):
            data.update(self.extra)
        data["instructions"] = FLAT_TONE_INSTRUCTIONS

        logger.bind(tag=TAG).info(
            "发起上游TTS请求: "
            f"url={self.api_url}, text_len={len(text)}, text_preview={text[:80]}, "
            f"voice={self.voice}, language={current_language}, task_type={self.task_type}, "
            f"format={self.audio_file_type}, instructions={data.get('instructions', '')}, "
            f"output_file={output_file or '<memory>'}"
        )
        response = requests.post(
            self.api_url, json=data, headers=headers, timeout=self.timeout
        )
        if response.status_code == 200:
            logger.bind(tag=TAG).info(
                "上游TTS响应成功: "
                f"status={response.status_code}, content_type={response.headers.get('content-type', '')}, "
                f"bytes={len(response.content)}"
            )
            if output_file:
                with open(output_file, "wb") as audio_file:
                    audio_file.write(response.content)
                logger.bind(tag=TAG).debug(
                    f"上游TTS音频已写入文件: output_file={output_file}"
                )
                return None
            return response.content

        logger.bind(tag=TAG).error(
            "上游TTS响应失败: "
            f"status={response.status_code}, body={response.text[:500]}"
        )
        raise Exception(
            f"上游TTS请求失败: {response.status_code} - {response.text}"
        )
