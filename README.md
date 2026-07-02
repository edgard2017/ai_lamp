# AI Lamp · 智能学习台灯

一盏给小朋友用的智能台灯：用摄像头看坐姿/握笔、用语音陪她做作业、循循善诱地引导
而不是直接给答案，并长期沉淀她的**错题集**与**能力画像**。

> 自己动手做，和小朋友一起完成。

## 设计原则（分层架构）

| 层 | 跑在哪 | 特点 | 负责什么 |
|----|--------|------|----------|
| **本地·常开** | 树莓派 | 免费、即时、不烧 token | 坐姿监测、握笔检测、UI 反馈 |
| **云端/自建·按需** | LLM / VLM | 事件触发、偶发 | 作业题理解、引导对话、错误归类、周报生成 |

核心思想和音频里的 **VAD 门控云端识别** 一样：廉价的本地检测常开，
昂贵的大模型只在「值得说话」的事件上点火。

## 当前进度

- ✅ **坐姿矫正（Stage 1）**：纯几何判定 + 个性化标定 + 防唠叨节流。
  - 算法层 `src/ai_lamp/vision/` 不依赖摄像头/MediaPipe，可在任意机器跑单测。
- ⏳ 规划中：握笔检测、语音对话、作业引导、错题集/能力画像（见 `docs/roadmap.md`）。

## 快速开始

### 1. 跑算法单测（任何机器，无需摄像头）
```bash
cd ai_lamp
python3 tests/test_posture_rules.py
python3 tests/test_monitor.py
```

### 2. 跑实时坐姿 demo（需要摄像头的机器，如树莓派）
```bash
pip install -r requirements.txt
python3 apps/posture_demo.py
# 按 c 标定（坐端正后采集基准），按 q 退出
```

## 目录结构

见 [docs/architecture.md](docs/architecture.md)。
