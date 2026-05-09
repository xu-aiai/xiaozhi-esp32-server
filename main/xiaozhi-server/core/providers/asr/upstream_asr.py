import os
import time
import requests

from typing import Optional, Tuple, List

from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.NON_STREAM
        self.api_key = (config.get("api_key") or "").strip()
        self.api_url = config.get(
            "base_url", "http://10.90.252.47:8020/v1/audio/transcriptions"
        )
        self.model = (config.get("model_name") or "").strip()
        self.language = (config.get("language") or "").strip()
        self.prompt = (config.get("prompt") or "").strip()
        self.response_format = (config.get("response_format") or "json").strip()
        self.output_dir = config.get("output_dir", "tmp/")
        self.timeout = float(config.get("timeout", 300))
        self.delete_audio_file = delete_audio_file

        os.makedirs(self.output_dir, exist_ok=True)
        logger.bind(tag=TAG).info(
            "初始化上游ASR: "
            f"url={self.api_url}, model={'<empty>' if not self.model else self.model}, "
            f"language={'<auto>' if not self.language else self.language}, "
            f"response_format={self.response_format}, timeout={self.timeout}s, "
            f"api_key={'set' if self.api_key else 'empty'}"
        )

    def requires_file(self) -> bool:
        return True

    async def speech_to_text(
        self,
        opus_data: List[bytes],
        session_id: str,
        audio_format="opus",
        artifacts=None,
    ) -> Tuple[Optional[str], Optional[str]]:
        if artifacts is None or not artifacts.file_path:
            logger.bind(tag=TAG).warning(
                f"上游ASR跳过识别: session_id={session_id}, 缺少音频文件"
            )
            return "", None

        file_path = artifacts.file_path
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = {"response_format": self.response_format}
        if self.model:
            data["model"] = self.model
        if self.language:
            data["language"] = self.language
        if self.prompt:
            data["prompt"] = self.prompt

        try:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
            logger.bind(tag=TAG).info(
                "发起上游ASR请求: "
                f"session_id={session_id}, url={self.api_url}, "
                f"file_path={file_path}, file_size={file_size}, "
                f"model={'<empty>' if not self.model else self.model}, "
                f"language={'<auto>' if not self.language else self.language}, "
                f"response_format={self.response_format}"
            )
            with open(file_path, "rb") as audio_file:
                files = {"file": ("audio.wav", audio_file, "audio/wav")}
                start_time = time.time()
                response = requests.post(
                    self.api_url,
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=self.timeout,
                )
                logger.bind(tag=TAG).debug(
                    f"上游ASR耗时: {time.time() - start_time:.3f}s | 状态: {response.status_code}"
                )

            response.raise_for_status()
            if self.response_format.lower() == "json":
                payload = response.json()
                text = payload.get("text", "")
                logger.bind(tag=TAG).info(
                    "上游ASR响应成功: "
                    f"session_id={session_id}, text_len={len(text)}, "
                    f"text_preview={text[:80]}"
                )
                return text, file_path

            text = response.text
            logger.bind(tag=TAG).info(
                "上游ASR文本响应成功: "
                f"session_id={session_id}, text_len={len(text)}, text_preview={text[:80]}"
            )
            return text, file_path
        except Exception as e:
            logger.bind(tag=TAG).error(
                "上游ASR识别失败: "
                f"session_id={session_id}, url={self.api_url}, "
                f"file_path={file_path}, error={e}"
            )
            return "", file_path
