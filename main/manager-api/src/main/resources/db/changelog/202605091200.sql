delete from `ai_model_provider` where id in ('SYSTEM_ASR_UpstreamASR', 'SYSTEM_TTS_UpstreamTTS');
insert into `ai_model_provider` (`id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`) values
('SYSTEM_ASR_UpstreamASR', 'ASR', 'upstream_asr', '上游语音识别', '[{"key":"base_url","label":"接口地址","type":"string"},{"key":"model_name","label":"模型名称","type":"string"},{"key":"api_key","label":"API密钥","type":"string"},{"key":"response_format","label":"响应格式","type":"string"},{"key":"prompt","label":"提示词","type":"string"},{"key":"language","label":"语种","type":"string"},{"key":"timeout","label":"超时时间(秒)","type":"number"},{"key":"output_dir","label":"输出目录","type":"string"}]', 1, 1, NOW(), 1, NOW()),
('SYSTEM_TTS_UpstreamTTS', 'TTS', 'upstream_tts', '上游语音合成', '[{"key":"api_url","label":"接口地址","type":"string"},{"key":"model","label":"模型名称","type":"string"},{"key":"api_key","label":"API密钥","type":"string"},{"key":"voice","label":"默认音色","type":"string"},{"key":"language","label":"语种","type":"string"},{"key":"task_type","label":"任务类型","type":"string"},{"key":"instructions","label":"语气说明","type":"string"},{"key":"speed","label":"语速","type":"number"},{"key":"format","label":"音频格式","type":"string"},{"key":"timeout","label":"超时时间(秒)","type":"number"},{"key":"output_dir","label":"输出目录","type":"string"}]', 1, 1, NOW(), 1, NOW());

delete from `ai_model_config` where id in ('ASR_UpstreamASR', 'TTS_UpstreamTTS');
insert into `ai_model_config` values
('ASR_UpstreamASR', 'ASR', 'UpstreamASR', '上游语音识别', 1, 1, '{"type": "upstream_asr", "base_url": "http://10.90.252.47:8020/v1/audio/transcriptions", "model_name": "", "api_key": "", "response_format": "json", "prompt": "请严格保留型号/编号的原始写法。\\n1) 字母与数字必须原样输出：数字用阿拉伯数字，不要转成中文数字。\\n2) 例如：AP50G3 必须输出为 AP50G3，不要输出为 AP五零G三。\\n3) 仅输出转写文本本身。", "language": "", "timeout": 300, "output_dir": "tmp/"}', NULL, '默认上游ASR，按 multipart/form-data 方式调用 /v1/audio/transcriptions', 1, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS', 'TTS', 'UpstreamTTS', '上游语音合成', 1, 1, '{"type": "upstream_tts", "api_url": "http://10.90.252.47:8091/v1/audio/speech", "model": "", "api_key": "", "voice": "vivian", "language": "Chinese", "task_type": "CustomVoice", "instructions": "Speak with a warm and friendly tone", "speed": 1, "format": "wav", "timeout": 300, "output_dir": "tmp/"}', NULL, '默认上游TTS，按 JSON 方式调用 /v1/audio/speech', 1, NULL, NULL, NULL, NULL);

delete from `ai_tts_voice` where tts_model_id = 'TTS_UpstreamTTS';
insert into `ai_tts_voice` values
('TTS_UpstreamTTS_0001', 'TTS_UpstreamTTS', 'vivian', 'vivian', '多语言', NULL, NULL, 1, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0002', 'TTS_UpstreamTTS', 'serena', 'serena', '多语言', NULL, NULL, 2, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0003', 'TTS_UpstreamTTS', 'uncle_fu', 'uncle_fu', '多语言', NULL, NULL, 3, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0004', 'TTS_UpstreamTTS', 'dylan', 'dylan', '多语言', NULL, NULL, 4, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0005', 'TTS_UpstreamTTS', 'eric', 'eric', '多语言', NULL, NULL, 5, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0006', 'TTS_UpstreamTTS', 'ryan', 'ryan', '多语言', NULL, NULL, 6, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0007', 'TTS_UpstreamTTS', 'aiden', 'aiden', '多语言', NULL, NULL, 7, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0008', 'TTS_UpstreamTTS', 'ono_anna', 'ono_anna', '多语言', NULL, NULL, 8, NULL, NULL, NULL, NULL),
('TTS_UpstreamTTS_0009', 'TTS_UpstreamTTS', 'sohee', 'sohee', '多语言', NULL, NULL, 9, NULL, NULL, NULL, NULL);

update `ai_model_config` set `is_default` = 0 where `model_type` in ('ASR', 'TTS');
update `ai_model_config` set `is_default` = 1, `is_enabled` = 1 where `id` in ('ASR_UpstreamASR', 'TTS_UpstreamTTS');

update `ai_agent_template`
set `asr_model_id` = 'ASR_UpstreamASR',
    `tts_model_id` = 'TTS_UpstreamTTS',
    `tts_voice_id` = 'TTS_UpstreamTTS_0001'
where `sort` = (
    select `min_sort`
    from (
        select min(`sort`) as `min_sort`
        from `ai_agent_template`
        where `sort` >= 0
    ) as `default_template`
);
