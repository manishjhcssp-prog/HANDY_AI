"""
JARVIS AI - Main Execution Entry Point
Interactive Console for JARVIS (Just A Rather Very Intelligent System).
Features multi-provider failover, real-time response streaming, and system diagnostics.
"""

import sys
import os
import asyncio
import argparse
from typing import Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from jarvis.brain.agent import JarvisAgent
from jarvis.audio.tts import TTSEngine
from jarvis.audio.stt import STTEngine
from jarvis.audio.recorder import AudioRecorder
from config.settings import settings


BANNER = r"""
 +===========================================================================+
 |                                                                           |
 |       ██╗  █████╗  ██████╗  ██╗   ██╗ ██╗ ███████╗                        |
 |       ██║ ██╔══██╗ ██╔══██╗ ██║   ██║ ██║ ██╔════╝                        |
 |       ██║ ███████║ ██████╔╝ ██║   ██║ ██║ ███████╗                        |
 |  ██   ██║ ██╔══██║ ██╔══██╗ ╚██╗ ██╔╝ ██║ ╚════██║                        |
 |  ╚█████╔╝ ██║  ██║ ██║  ██║  ╚████╔╝  ██║ ███████║                        |
 |   ╚════╝  ╚═╝  ╚═╝ ╚═╝  ╚═╝   ╚═══╝   ╚═╝ ╚══════╝                        |
 |                                                                           |
 |           Just A Rather Very Intelligent System (Windows Core)            |
 +===========================================================================+
"""


def print_system_info(agent: JarvisAgent, voice_enabled: bool = False):
    """Prints system status and active provider configuration."""
    print(BANNER)
    print(" [SYSTEM INITIALIZATION & DIAGNOSTICS]")
    print(f" • Free-Only Cost Guard : {'ENABLED (Target ₹0 ongoing cost)' if settings.free_only_mode else 'DISABLED'}")
    voice_status = "ENABLED" if voice_enabled else "DISABLED (Use --voice or type 'voice on')"
    print(f" • Voice Audio Feedback : {voice_status}")
    print(f" • Provider Priority    : {' -> '.join(settings.provider_priority)}")
    
    masked_summary = settings.get_masked_keys_summary()
    print(" • Registered API Keys  :")
    for provider, keys in masked_summary.items():
        if keys:
            print(f"   - {provider.upper():<12}: {', '.join(keys)} ({len(keys)} key{'s' if len(keys) > 1 else ''})")
        else:
            status = "Local / Offline" if provider == "ollama" else "No keys registered"
            print(f"   - {provider.upper():<12}: [{status}]")
    
    print("-" * 75)
    print(" Commands: 'voice on/off', 'listen', 'status', 'clear', 'exit' or 'quit'.")
    print("-" * 75)


async def interactive_loop(agent: JarvisAgent, voice_enabled: bool = False):
    """Runs the main interactive conversational loop with JARVIS."""
    tts = TTSEngine(voice=settings.audio_config.get("tts", {}).get("voice", "en-GB-RyanNeural"))
    stt = STTEngine()
    recorder = AudioRecorder()
    voice_active = voice_enabled

    print_system_info(agent, voice_active)
    
    # Initial spoken introduction
    print("\nJARVIS: Initializing neural subsystems, sir...\n")
    try:
        greeting_text = ""
        print("JARVIS > ", end="", flush=True)
        async for chunk in agent.stream_chat("Please greet the user warmly and confirm you are online and ready to assist."):
            print(chunk, end="", flush=True)
            greeting_text += chunk
        print("\n")
        if voice_active:
            await tts.speak_text(greeting_text)
    except Exception as e:
        print(f"\n[Error contacting neural router: {e}]\n")

    while True:
        try:
            user_input = input("User > ").strip()
        except (KeyboardInterrupt, EOFError):
            farewell = "Powering down neural links. Have a pleasant day, sir."
            print(f"\n\nJARVIS: {farewell}")
            if voice_active:
                tts.speak_sync(farewell)
            break

        if not user_input:
            if voice_active:
                # In voice mode, pressing Enter triggers microphone listening
                print("\n[🎤 Microphone active - Speak now... (auto-stops on silence)]")
                audio = recorder.record_until_silence(max_duration=10.0)
                if len(audio) == 0:
                    print("[No speech captured or microphone unavailable.]\n")
                    continue
                print("[⚡ Transcribing speech with Whisper...]")
                transcribed = stt.transcribe(audio)
                if not transcribed:
                    print("[Could not recognize speech. Please speak closer to microphone.]\n")
                    continue
                print(f"User (Spoken) > {transcribed}\n")
                user_input = transcribed
            else:
                continue

        cmd = user_input.lower()
        if cmd in ("exit", "quit", "q", "bye"):
            farewell = "Powering down subsystems. Until next time, sir."
            print(f"\nJARVIS: {farewell}\n")
            if voice_active:
                tts.speak_sync(farewell)
            break
        elif cmd in ("clear", "/clear", "cls"):
            agent.reset()
            print("\n[System memory cleared. Starting fresh session.]\n")
            continue
        elif cmd == "voice on":
            voice_active = True
            msg = "Voice audio feedback enabled, sir."
            print(f"\nJARVIS: {msg}\n")
            tts.speak_sync(msg)
            continue
        elif cmd == "voice off":
            voice_active = False
            print("\nJARVIS: Voice audio feedback disabled. Text-only mode active, sir.\n")
            continue
        elif cmd in ("listen", "mic", "/listen"):
            print("\n[🎤 Microphone active - Speak now... (auto-stops on silence)]")
            audio = recorder.record_until_silence(max_duration=10.0)
            if len(audio) == 0:
                print("[No speech captured or microphone unavailable.]\n")
                continue
            print("[⚡ Transcribing speech with Whisper...]")
            transcribed = stt.transcribe(audio)
            if not transcribed:
                print("[Could not recognize speech. Please speak closer to microphone.]\n")
                continue
            print(f"User (Spoken) > {transcribed}\n")
            user_input = transcribed
        elif cmd in ("status", "/status"):
            telemetry = agent.get_status()
            print("\n--- [TELEMETRY & ROUTER STATUS] ---")
            print(f" Active Provider  : {telemetry.get('active_provider') or 'Standby'}")
            print(f" Active Model     : {telemetry.get('active_model') or 'Standby'}")
            print(f" Active Key       : {telemetry.get('active_key_masked') or 'None'}")
            print(f" Cost Protection  : {telemetry.get('free_only_mode')}")
            print(f" Voice Mode       : {'Active' if voice_active else 'Disabled'}")
            print(" Key Pool Status  :")
            for p, pool in telemetry.get("key_manager", {}).items():
                total = pool.get("total_keys", 0)
                avail = pool.get("available_keys", 0)
                status_summary = f"{avail}/{total} Active" if total > 0 else "[Offline / Local]"
                print(f"   • {p:<12}: {status_summary}")
            print("-----------------------------------\n")
            continue

        # Normal query processing
        print("JARVIS > ", end="", flush=True)
        try:
            if voice_active and tts:
                await tts.stream_and_speak(
                    agent.stream_chat(user_input),
                    on_token=lambda chunk: print(chunk, end="", flush=True),
                )
            else:
                async for chunk in agent.stream_chat(user_input):
                    print(chunk, end="", flush=True)
            print("\n")
        except Exception as e:
            print(f"\n[Router Alert: {e}]\n")


async def one_shot_query(agent: JarvisAgent, query: str, voice_enabled: bool = False):
    """Executes a single query and prints the streamed answer."""
    tts = TTSEngine() if voice_enabled else None
    print(f"User: {query}\n")
    print("JARVIS: ", end="", flush=True)
    try:
        if voice_enabled and tts:
            await tts.stream_and_speak(
                agent.stream_chat(query),
                on_token=lambda chunk: print(chunk, end="", flush=True),
            )
        else:
            async for chunk in agent.stream_chat(query):
                print(chunk, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[Router Alert: {e}]\n")


def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomous AI Assistant")
    parser.add_argument("--query", "-q", type=str, help="Execute a single one-shot query and exit")
    parser.add_argument("--status", "-s", action="store_true", help="Print system telemetry and exit")
    parser.add_argument("--voice", "-v", action="store_true", help="Enable spoken voice output")
    args = parser.parse_args()

    agent = JarvisAgent()

    if args.status:
        print_system_info(agent, voice_enabled=args.voice)
        return

    if args.query:
        asyncio.run(one_shot_query(agent, args.query, voice_enabled=args.voice))
        return

    asyncio.run(interactive_loop(agent, voice_enabled=args.voice))


if __name__ == "__main__":
    main()

