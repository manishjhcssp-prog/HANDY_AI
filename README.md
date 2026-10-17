# ⚡ J.A.R.V.I.S. // Autonomous AI Workstation Assistant (Mark VII)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-00f0ff.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-0077ff.svg?style=flat-square)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/tests-38%20passed-10b981.svg?style=flat-square)](tests/)
[![Strict ₹0 Cost Guard](https://img.shields.io/badge/API%20Cost-₹0%20(Free%20Tier)-ffb700.svg?style=flat-square)](config/config.yaml)
[![Holographic HUD](https://img.shields.io/badge/HUD-FastAPI%20%2B%20WebSockets-a855f7.svg?style=flat-square)](hud/)

> **Architectural Blueprint**: All modifications strictly adhere to [JARVIS_MASTER_PLAN.md](file:///d:/SERVAM_AI/JARVIS_MASTER_PLAN.md).

---

## 🌟 Overview

**JARVIS (Just A Rather Very Intelligent System)** is a voice-first, low-latency autonomous AI assistant engineered for Windows workstations. Built with a polite British butler demeanor, it operates under a **strict ₹0 ongoing API cost constraint** through an intelligent multi-provider cognitive router with multi-key pooling, automatic cooldown recovery, and seamless provider failover.

JARVIS features a **60 FPS Sci-Fi Holographic Web HUD** with a canvas-rendered Arc Reactor core, real-time hardware telemetry gauges, low-latency streaming **Kokoro Neural TTS** (82M parameters), **Faster-Whisper STT**, and a sub-20ms OS automation engine for controlling volume, applications, and web platforms.

---

## 🚀 Key Features

### 🧠 1. Cognitive Neural Router & ₹0 Cost Guard
* **Free-First Failover Priority**:
  1. **Groq** (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`) — Ultra-low latency (~117ms TTFT)
  2. **OpenRouter** (`openrouter/free`, `meta-llama/llama-3.3-70b-instruct:free`, `google/gemini-2.0-flash-exp:free`)
  3. **Google Gemini** (`gemini-2.0-flash`, `gemini-1.5-flash`)
  4. **Local Ollama** (100% offline, private fallback)
  5. **Sarvam AI** (Indic speech & language tasks)
* **Multi-Key Pooling & Rotation**: Supports multiple API keys per provider (e.g. `GROQ_API_KEY_1`, `GROQ_API_KEY_2`) with round-robin rotation, exponential backoff on HTTP 429 rate limits, and automatic quarantine of invalid keys.
* **Persistent Keep-Alive Connections**: HTTP connection pooling reduces network handshake overhead to zero.

### 🎙️ 2. High-Fidelity Voice Pipeline (Ears & Mouth)
* **Neural Text-to-Speech (Mouth)**:
  - Powered by **Kokoro-82M** running locally at 24kHz with the `bm_george` British accent.
  - Sentence-level concurrent streaming pipeline: synthesizes audio while LLM tokens are still streaming.
  - Native fallback to **Windows SAPI5** (`Microsoft David`) for 100% offline reliability.
* **Speech-to-Text (Ears)**:
  - Microphone capture with RMS energy-based Voice Activity Detection (VAD) that auto-stops on silence.
  - Local speech transcription via **Faster-Whisper** (`base.en` / `small.en`) with CPU int8 quantization.

### ⚙️ 3. Sub-20ms OS Automation & Fast-Path Tools
* **Desktop Application Launcher**: Instant local execution of Chrome, VS Code, Notepad, Calculator, Terminal, Task Manager, Settings, Spotify, Steam, etc.
* **Web Services & Streaming Platforms**: Direct native browser launching for **Crunchyroll**, **YouTube**, **Netflix**, **Prime Video**, **Discord**, **WhatsApp Web**, **GitHub**, **Reddit**, **Twitter/X**, and arbitrary URLs.
* **Hardware Telemetry**: Real-time CPU core load, RAM usage (GB/total), Primary Disk (C:) storage, battery percent, and power plug status via `psutil`.
* **Media & Volume Control**: Volume up/down, mute toggle, media play/pause, next track, and previous track via Windows virtual keys.
* **Web Search**: DuckDuckGo search integration with automatic RSS news fallback.

### 🌐 4. Sci-Fi Holographic HUD (Tier 4)
* **Futuristic Glassmorphic Interface**:
  - Deep Obsidian (`#050811`), Neon Cyan (`#00f0ff`), Quantum Blue (`#0077ff`), and Core Gold (`#ffb700`) aesthetics.
  - Full-screen animated holographic scanlines and particle dust background.
* **Arc Reactor Plasma Core**:
  - 60 FPS interactive HTML5 canvas engine.
  - Triple counter-rotating magnetic confinement rings, 10 copper/cyan energy coils, and central pulsing plasma core.
  - Core animation dynamically accelerates and shifts colors based on agent state (`IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`).
* **Real-Time Telemetry Gauges**:
  - Circular SVG radial meters for CPU and RAM load.
  - Linear progress bars for storage capacity and battery.
  - Live API key pool monitor and round-trip ping counter.
* **Tactical Terminal & Dialogue Stream**:
  - Token-by-token typewriter chat stream with glowing sender badges.
  - Real-time monospace terminal log capturing system calls and router events.
  - One-click quick directive pills (`Crunchyroll`, `Chrome`, `Calculator`, `YouTube`, `System Status`, `Weather`).

---

## 📂 Project Structure

```text
d:\SERVAM_AI/
├── JARVIS_MASTER_PLAN.md      # Master architectural specification
├── README.md                  # Project documentation & quickstart
├── requirements.txt           # Python package dependencies
├── run_jarvis.py              # Main multi-mode CLI & HUD launcher
├── config/
│   ├── config.yaml            # Persona, provider priority & model configs
│   └── settings.py            # Environment variable loader & key manager
├── hud/                       # Futuristic Sci-Fi Web Interface
│   ├── index.html             # HUD layout & Arc Reactor canvas
│   ├── styles.css             # Glassmorphic sci-fi styling
│   └── app.js                 # WebSocket client & Arc Reactor canvas engine
├── jarvis/
│   ├── audio/                 # Audio Subsystem (STT, TTS, Recorder)
│   │   ├── recorder.py        # Mic capture & RMS energy VAD
│   │   ├── stt.py             # Whisper STT engine
│   │   └── tts.py             # Kokoro Neural TTS & Windows SAPI engine
│   ├── brain/                 # Cognitive Brain & Orchestrator
│   │   ├── agent.py           # JarvisAgent conversation loop & fast-path tools
│   │   ├── prompts.py         # System persona & British butler matrix
│   │   ├── router.py          # LLMRouter with multi-provider failover
│   │   ├── key_manager.py     # Multi-key rotation pool & rate limiter
│   │   └── adapters/          # Groq, OpenRouter, Gemini, Ollama, Sarvam
│   ├── server/                # Backend API & WebSocket Bridge
│   │   └── app.py             # FastAPI server & background telemetry daemon
│   └── tools/                 # OS Automation Tools
│       ├── os_control.py      # App launcher, streaming URLs & media keys
│       ├── sys_info.py        # CPU, RAM, battery & hardware metrics
│       ├── web_tools.py       # DuckDuckGo search & weather
│       └── registry.py        # Centralized tool dispatch & schemas
└── tests/                     # Comprehensive Unit & Mock Test Suite
    ├── test_adapters.py       # Provider adapters & cost guards
    ├── test_audio.py          # STT, TTS & Kokoro voice tests
    ├── test_key_manager.py    # Key rotation & cooldown recovery
    ├── test_router_failover.py# Multi-provider failover scenarios
    ├── test_server.py         # FastAPI REST & WebSocket endpoints
    └── test_tools.py          # OS control, Crunchyroll & sys info tests
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* **Windows 10 / 11** (64-bit)
* **Python 3.10+** (Tested on Python 3.11)
* Working microphone and speakers / headphones

### 2. Clone the Repository
```powershell
git clone https://github.com/manishjhcssp-prog/HANDY_AI.git
cd HANDY_AI
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Add your free API keys in `.env` (multiple keys per provider are supported by adding `_1`, `_2`, etc.):
```env
# Groq (Recommended - Primary Free Provider)
GROQ_API_KEY_1=gsk_...
GROQ_API_KEY_2=gsk_...

# OpenRouter (Fallback Free Provider)
OPENROUTER_API_KEY_1=sk-or-v1-...

# Google Gemini (Reasoning & Vision)
GEMINI_API_KEY_1=AIzaSy...
```

---

## 🎮 How to Run JARVIS

### 1. Sci-Fi Holographic Web HUD (Recommended)
Launch the FastAPI server and open the 60 FPS interactive HUD in your default web browser:
```powershell
python run_jarvis.py --hud
```
* **HUD URL**: `http://127.0.0.1:8000`
* **Interactive API Docs**: `http://127.0.0.1:8000/docs`
* **WebSocket Stream**: `ws://127.0.0.1:8000/ws`

### 2. Spoken Voice Interactive CLI Mode
Run JARVIS in voice mode with real-time microphone listening and Kokoro neural vocal output:
```powershell
python run_jarvis.py --voice
```
* Press **Enter** to speak into the microphone (auto-stops on silence).
* Type commands or talk naturally.
* Type `voice off` to switch to text mode, or `voice on` to re-enable voice.

### 3. Text Interactive Mode
```powershell
python run_jarvis.py
```

### 4. One-Shot Query Execution
Execute a single directive directly from PowerShell without entering the interactive loop:
```powershell
# Open a web platform / app
python run_jarvis.py --query "Open Crunchyroll"
python run_jarvis.py --query "Open Chrome"
python run_jarvis.py --query "Open calculator"

# Check system telemetry
python run_jarvis.py --query "System status"

# Search web news
python run_jarvis.py --query "Search web for latest AI news"
```

### 5. Check System Telemetry & Key Pool Status
```powershell
python run_jarvis.py --status
```

---

## 🧪 Automated Test Suite

Run the full automated test suite (all 33 unit and mock tests pass in < 8 seconds with ₹0 API usage):
```powershell
python -m pytest tests/ -v
```

```text
============================= test session starts =============================
tests/test_adapters.py::test_openrouter_free_model_eligibility PASSED
tests/test_adapters.py::test_groq_free_model_eligibility PASSED
tests/test_adapters.py::test_gemini_free_model_eligibility PASSED
tests/test_adapters.py::test_ollama_all_models_free PASSED
tests/test_adapters.py::test_sarvam_free_model_eligibility PASSED
tests/test_audio.py::test_tts_text_sanitization PASSED
tests/test_audio.py::test_kokoro_tts_initialization PASSED
tests/test_key_manager.py::test_rate_limiting_cooldown_and_recovery PASSED
tests/test_router_failover.py::test_scenario_1_primary_key_429_second_key_succeeds PASSED
tests/test_server.py::test_server_status_endpoint PASSED
tests/test_server.py::test_server_telemetry_endpoint PASSED
tests/test_server.py::test_serve_hud_index PASSED
tests/test_tools.py::test_launch_application PASSED
tests/test_tools.py::test_agent_direct_launcher PASSED
============================= 38 passed in 8.5s ===============================
```

---

## 🗺️ Roadmap & Implementation Status

| Phase | Milestone | Deliverables | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1A** | **Cognitive Router Core** | Multi-provider failover (Groq / OpenRouter / Gemini / Ollama / Sarvam), multi-key rotation pool, ₹0 cost guard, `JarvisAgent` conversation loop | 🟢 Completed |
| **Phase 1B** | **Voice Pipeline** | Streaming Kokoro-82M Neural TTS (24kHz `bm_george`), Windows SAPI5 fallback, Faster-Whisper STT, RMS energy VAD | 🟢 Completed |
| **Phase 2** | **OS Automation & Tools** | Volume / media controls, universal app & streaming web launcher (Crunchyroll, YouTube, Chrome, Calc, etc.), hardware telemetry, DuckDuckGo search | 🟢 Completed |
| **Phase 3** | **Sci-Fi Holographic HUD** | FastAPI backend, WebSocket bidirectional sync, 60 FPS Arc Reactor Canvas, SVG radial gauges, tactical terminal | 🟢 Completed |
| **Phase 4** | **Vision & Long-Term Memory** | Screen awareness (`mss` + vision LLM), SQLite episodic & preference store (`MemoryManager`), user preference tracking & context injection | 🟢 Completed |
| **Phase 5** | **Wake-Word & Autonomy** | Background wake-word listening (`openWakeWord`), proactive desktop reminders, Windows background service | 🟡 Ready to Begin |

---

## 📜 License
MIT License. Built with ❤️ by the community.
