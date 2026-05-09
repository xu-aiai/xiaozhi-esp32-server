# 语音链路详细设计

## 1. 目标

本文档描述当前项目中接入自定义上游语音服务的详细设计，覆盖以下内容：

- 自定义上游 `ASR` 设计
- 自定义上游 `TTS` 设计
- 默认模型切换策略
- 智控台配置方式
- 运行时调用链路
- 日志与排障设计

本设计的目标是：

- 默认使用我们自定义的上游 `ASR` 和 `TTS`
- 保留现有其他模型，继续支持在智控台中配置与切换
- 当上游接口异常时，可以通过日志快速定位问题

## 2. 设计范围

本次设计涉及以下模块：

- Python 服务端 `main/xiaozhi-server`
- Java 管理端 `main/manager-api`
- 智控台模型配置数据
- 本地默认配置 `main/xiaozhi-server/config.yaml`

本次设计不包含以下内容：

- ESP32 设备侧协议改造
- LLM、VAD、Memory 等非语音模块改造
- TTS WebSocket 流式接口的默认接入实现

## 3. 上游服务定义

### 3.1 ASR

上游 ASR 服务地址：

- `http://10.90.252.47:8020/v1/audio/transcriptions`

协议：

- `POST`
- `multipart/form-data`

关键字段：

- `file`
- `response_format`
- `model`
- `language`
- `prompt`

返回：

- JSON，主要关注 `text`

### 3.2 TTS

上游 TTS HTTP 服务地址：

- `http://10.90.252.47:8091/v1/audio/speech`

协议：

- `POST`
- `application/json`

关键字段：

- `input`
- `voice`
- `language`
- `response_format`
- `task_type`
- `stream`
- `instructions`
- `model`

返回：

- 音频二进制

### 3.3 TTS WebSocket 流式

上游 TTS 流式地址：

- `ws://10.90.252.47:8091/v1/audio/speech/stream`

当前状态：

- 已纳入设计说明
- 当前默认实现仍使用 HTTP TTS
- 后续如需启用流式上游，可在现有自定义 TTS provider 基础上继续扩展

## 4. 总体架构

### 4.1 模块分层

语音链路由三层组成：

1. 配置层
   - 本地 `config.yaml`
   - 智控台 `ai_model_provider` / `ai_model_config`
2. Provider 适配层
   - `core/providers/asr/upstream_asr.py`
   - `core/providers/tts/upstream_tts.py`
3. 运行时调用层
   - `modules_initialize.py`
   - `ConnectionHandler`
   - `ASRProviderBase`
   - `TTSProviderBase`

### 4.2 默认策略

默认策略分两部分：

1. Python 本地默认配置切换
   - `selected_module.ASR = UpstreamASR`
   - `selected_module.TTS = UpstreamTTS`
2. 智控台默认模型切换
   - 将 `ASR_UpstreamASR` 设为默认模型
   - 将 `TTS_UpstreamTTS` 设为默认模型
   - 将默认智能体模板的 `asr_model_id` 和 `tts_model_id` 更新为上述模型

这样做的效果是：

- 单模块运行时默认走自定义上游模型
- 全模块运行时，智控台默认模板创建的新智能体也会默认走自定义上游模型
- 其他模型仍然保留，可继续在界面上手动切换

## 5. ASR 详细设计

### 5.1 代码位置

- `main/xiaozhi-server/core/providers/asr/upstream_asr.py`

### 5.2 实现类型

`UpstreamASR` 是一个非流式 `ASR provider`：

- `interface_type = NON_STREAM`

它依赖框架基类完成以下工作：

- 接收设备上送的 Opus 音频
- 解码为 PCM
- 生成 WAV 临时文件
- 调用 `speech_to_text()`

### 5.3 请求构造

`UpstreamASR` 会向上游发起一个 `multipart/form-data` 请求。

请求头：

- 如果配置了 `api_key`，则增加：
  - `Authorization: Bearer {api_key}`

表单字段：

- `file`
- `response_format`
- `model`，仅配置了 `model_name` 时发送
- `language`，仅配置了 `language` 时发送
- `prompt`，仅配置了 `prompt` 时发送

### 5.4 返回处理

当 `response_format = json` 时：

- 读取 JSON
- 提取 `text`
- 返回给下游对话流程

当 `response_format` 不是 `json` 时：

- 直接读取 `response.text`

### 5.5 配置项

支持的配置项如下：

- `base_url`
- `api_key`
- `model_name`
- `response_format`
- `prompt`
- `language`
- `timeout`
- `output_dir`

### 5.6 设计取舍

当前实现选择非流式 ASR，原因是：

- 上游协议是典型 OpenAI 兼容文件上传接口
- 与现有 `ASRProviderBase` 契合度最高
- 对现有录音结束判定逻辑侵入最小

## 6. TTS 详细设计

### 6.1 代码位置

- `main/xiaozhi-server/core/providers/tts/upstream_tts.py`

### 6.2 实现类型

`UpstreamTTS` 当前是一个非流式 `TTS provider`：

- 通过 HTTP 一次性生成整段音频
- 返回完整音频字节
- 再由现有 `TTSProviderBase` 完成切包、编码和下发

### 6.3 请求构造

请求方式：

- `POST`
- `application/json`

请求头：

- `Content-Type: application/json`
- 如果配置了 `api_key`，则增加：
  - `Authorization: Bearer {api_key}`

请求体：

- `input`
- `voice`
- `language`
- `response_format`
- `task_type`
- `stream = false`
- `instructions`
- `speed`
- `model`，仅配置时发送
- `extra` 中的自定义顶层字段

### 6.4 返回处理

返回值为音频二进制：

- 如果调用方要求写文件，落盘到 `output_file`
- 否则直接返回音频字节数组

### 6.5 配置项

支持的配置项如下：

- `api_url`
- `api_key`
- `model`
- `voice`
- `language`
- `task_type`
- `instructions`
- `speed`
- `format`
- `timeout`
- `output_dir`
- `extra`

### 6.6 为什么默认不用 WebSocket 流式 TTS

虽然上游已经提供了流式 TTS WebSocket 接口，但当前默认实现仍选择 HTTP 版本，原因如下：

1. 当前项目已有完整稳定的“整段音频生成后再编码下发”链路
2. HTTP TTS 接入简单，改动范围小
3. 先保证默认链路稳定可用，再逐步演进到新的流式协议
4. 避免第一轮改造就同时变更“上游协议”和“本地下发时序”

后续如果需要接入流式 TTS，建议新增 `upstream_tts_stream.py`，而不是直接破坏当前稳定版本。

## 7. 智控台配置设计

### 7.1 数据表

涉及的表：

- `ai_model_provider`
- `ai_model_config`
- `ai_tts_voice`
- `ai_agent_template`

### 7.2 新增 Provider

数据库迁移新增两个 provider：

- `SYSTEM_ASR_UpstreamASR`
- `SYSTEM_TTS_UpstreamTTS`

其中：

- `ASR` provider 暴露上游语音识别所需字段
- `TTS` provider 暴露上游语音合成所需字段

### 7.3 新增默认模型

数据库迁移新增两个模型配置：

- `ASR_UpstreamASR`
- `TTS_UpstreamTTS`

并设置：

- `is_default = 1`
- `is_enabled = 1`

### 7.4 默认模板更新

迁移会更新默认智能体模板：

- `asr_model_id = ASR_UpstreamASR`
- `tts_model_id = TTS_UpstreamTTS`
- `tts_voice_id = TTS_UpstreamTTS_0001`

更新范围仅限默认模板，不会全量覆盖所有模板。

### 7.5 其他模型的保留策略

本设计不会删除或禁用其他 ASR/TTS 模型。

因此：

- 智控台依然可以修改其他模型配置
- 智能体依然可以手工切换回其他模型
- 默认值变更不影响已有模型的可用性

## 8. 本地配置设计

### 8.1 `config.yaml`

本地默认配置新增：

- `ASR.UpstreamASR`
- `TTS.UpstreamTTS`

并修改：

- `selected_module.ASR = UpstreamASR`
- `selected_module.TTS = UpstreamTTS`

### 8.2 `data/.config.yaml`

如果用户使用单模块部署，可以在 `data/.config.yaml` 中覆盖以下字段：

- ASR 地址
- TTS 地址
- API Key
- Prompt
- 默认音色
- 语言
- 语速

### 8.3 智控台模式

如果是全模块部署并使用智控台：

- Python 服务端会从 `manager-api` 拉取模型配置
- 智控台中的模型配置优先级高于本地默认模板

## 9. 运行时调用流程

### 9.1 ASR 流程

1. 设备通过 WebSocket 上传音频包
2. 服务端累积音频并在合适时机判定“说话结束”
3. `ASRProviderBase` 将 Opus 解码为 PCM
4. 框架生成 WAV 文件
5. `UpstreamASR.speech_to_text()` 向上游发起 HTTP 请求
6. 获取 `text`
7. 将识别结果送入后续 LLM 对话链路

### 9.2 TTS 流程

1. LLM 生成回复文本
2. 文本被送入 `UpstreamTTS`
3. `UpstreamTTS.text_to_speak()` 向上游发起 HTTP 请求
4. 获取完整音频字节
5. 本地将音频转为 Opus 包
6. 通过 WebSocket 把音频发送回设备

## 10. 日志与排障设计

### 10.1 设计目标

当 `ASR` 或 `TTS` 不通时，需要能够快速判断问题属于哪一层：

- 模块未被选中
- provider 未初始化成功
- 请求未发出
- 上游接口不可达
- 上游返回非 200
- 返回结构不符合预期
- 音频为空

### 10.2 已增加的关键日志

#### ASR

- 初始化日志
  - URL
  - model
  - language
  - response_format
  - timeout
  - key 是否存在
- 请求发起日志
  - `session_id`
  - 文件路径
  - 文件大小
  - 目标 URL
- 响应成功日志
  - 状态
  - 耗时
  - 文本长度
  - 文本预览
- 异常日志
  - `session_id`
  - URL
  - 文件路径
  - 错误信息

#### TTS

- 初始化日志
  - URL
  - model
  - voice
  - language
  - task_type
  - format
  - speed
  - timeout
  - key 是否存在
- 请求发起日志
  - 文本长度
  - 文本预览
  - 输出目标
- 响应成功日志
  - 状态
  - `content-type`
  - 音频字节数
- 异常日志
  - 状态码
  - 返回体摘要

#### 模块初始化

- 当前启用的 `ASR/TTS` 模块名
- 当前使用的 `type`

### 10.3 排障建议

排查顺序建议如下：

1. 看初始化日志
   - 确认实际选中的模型是不是 `UpstreamASR` / `UpstreamTTS`
2. 看请求发起日志
   - 如果没有，说明请求根本没走到 provider
3. 看 HTTP 状态码
   - 重点关注 `401`、`403`、`404`、`500`
4. 看返回结构
   - ASR 是否返回 `text`
   - TTS 是否真的返回音频字节
5. 看音频大小
   - 如果 TTS 返回 200 但字节数异常小，优先怀疑上游返回内容不是真实音频

## 11. 风险与后续演进

### 11.1 当前风险

1. 上游 ASR/TTS 网络依赖外部服务
2. TTS 默认仍为非流式，首包时延取决于上游整段生成速度
3. 如果上游字段协议变化，provider 需要同步调整

### 11.2 后续建议

1. 新增上游 WebSocket 流式 TTS provider
2. 增加健康检查或自检脚本
3. 为上游 ASR/TTS 增加集成测试
4. 在智控台中增加“连接测试”能力

## 12. 相关文件

Python：

- `main/xiaozhi-server/core/providers/asr/upstream_asr.py`
- `main/xiaozhi-server/core/providers/tts/upstream_tts.py`
- `main/xiaozhi-server/core/utils/modules_initialize.py`
- `main/xiaozhi-server/config.yaml`

Java / SQL：

- `main/manager-api/src/main/resources/db/changelog/202605091200.sql`
- `main/manager-api/src/main/resources/db/changelog/db.changelog-master.yaml`

## 13. 结论

当前设计已经满足以下目标：

- 默认切换到自定义上游 `ASR` 与 `TTS`
- 保留原有模型与界面配置能力
- 提供清晰的 provider 隔离层
- 在关键节点补齐排障日志

后续如果需要引入上游流式 TTS，可以在当前结构上继续演进，而不需要推翻现有实现。
