"""语音能力（火山·豆包语音）：TTS 合成、ASR 识别。

与豆包 LLM（方舟 ARK）是**两套凭证**：
  VOLC_SPEECH_APPID     应用 APP ID（非机密）
  VOLC_SPEECH_APIKEY    新版控制台 API Key（机密！只放 .env，别贴聊天/入库）
  VOLC_TTS_VOICE        音色代号（如 BV007_streaming）
  VOLC_TTS_RESOURCE_ID  V3 接口资源号（经典 BV 音色用 volc.tts.default）
"""
