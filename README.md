# 🤖 JARVIS: Intelligent Voice & System AI Assistant

> **MANDATORY**: Before making any modification, always read [JARVIS_MASTER_PLAN.md](file:///d:/SERVAM_AI/JARVIS_MASTER_PLAN.md).

---

## 🌟 Overview
JARVIS is a voice-first, low-latency, multimodal AI assistant designed for Windows OS with a **strict target ₹0 ongoing API cost**. It features an Intelligent Multi-Provider Router with automatic multi-key rotation and zero-delay failover across free-tier AI engines.

---

## 🏗️ Architecture & Features

### 1. Intelligent Multi-Provider LLM Router
* **Primary Provider**: OpenRouter (Default: `openrouter/free` auto-router or free open models)
* **Failover Sequence**:
  1. **OpenRouter** (Primary free open models)
  2. **Groq** (Ultra-low latency Llama 3)
  3. **Google Gemini** (Reasoning & vision)
  4. **Local Ollama** (100% offline, private)
  5. **Sarvam AI** (Indic speech & language tasks)
* **Multi-Key Pool & Rotation**:
  * Supports multiple keys per provider (e.g. `OPENROUTER_API_KEY_1`, `OPENROUTER_API_KEY_2`, etc.).
  * Automatic rotation on HTTP 429 rate limits with cooldown timers.
  * Automatic permanent disabling of invalid/unauthorized keys (401/403).
* **Cost Protection**: Target ₹0 ongoing API cost — blocks paid models automatically.
* **Security**: API keys are masked (`sk-or...7890`) and never exposed in logs or frontend code.

---

## 🚀 Quickstart & Configuration

### 1. Environment Setup
Copy the environment template:
```powershell
cp .env.example .env
```
Fill in your free API keys for the providers you wish to activate in `.env`.

### 2. Run Automated Verification Tests
Run the mock test suite to verify key rotation, failovers, and cost protection:
```powershell
python -m pytest tests/ -v
```
All 23 unit & mock test scenarios execute in < 2 seconds without consuming paid quota.

---

## 📚 Roadmap
* [x] **Phase 1**: Intelligent Multi-Provider LLM Router, Multi-Key Rotation Pool, ₹0 Cost Guard & Interactive CLI (`run_jarvis.py`)
* [x] **Phase 2**: Audio & Voice Pipeline (Microphone capture with RMS VAD, Faster-Whisper local STT & Streaming TTS with Windows SAPI / Neural voice fallback)
* [x] **Phase 3**: Windows OS Controller & Agent Tools (Master volume, media keys, app launcher, CPU/RAM/Disk/Battery metrics, DuckDuckGo & Weather tools)
* [ ] **Phase 4**: Sci-Fi Holographic HUD (Animated Arc Reactor, Audio Reactive Visualizer & Telemetry Web UI)
* [ ] **Phase 5**: Multimodal Vision & Persistent Vector Memory
