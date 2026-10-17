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
        print("JARVIS > ", end="", flush=True)
        if voice_active and tts:
            await tts.stream_and_speak(
                agent.stream_chat("Please greet the user warmly and confirm you are online and ready to assist."),
                on_token=lambda chunk: print(chunk, end="", flush=True),
            )
        else:
            async for chunk in agent.stream_chat("Please greet the user warmly and confirm you are online and ready to assist."):
                print(chunk, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[Error contacting neural router: {e}]\n")

    while True:
        try:
            raw_input = await asyncio.to_thread(input, "User > ")
            user_input = raw_input.strip()
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


async def autonomous_wake_word_loop(agent: JarvisAgent):
    """
    Continuous hands-free loop that runs in the background.
    Detects 'Hey JARVIS' wake-word, chimes, records user speech,
    executes directives, speaks response, and returns to standby.
    """
    from jarvis.audio.wake_word import WakeWordListener
    from jarvis.audio.recorder import AudioRecorder
    from jarvis.audio.stt import STTEngine
    from jarvis.audio.tts import TTSEngine
    from jarvis.tools.reminders import get_reminder_scheduler

    recorder = AudioRecorder()
    stt = STTEngine()
    tts = TTSEngine()

    # Start proactive reminder scheduler with TTS alert callback
    scheduler = get_reminder_scheduler()
    scheduler.register_alert_callback(lambda item: asyncio.create_task(
        tts.speak_text(f"Sir, an alert from your scheduler: {item['message']}")
    ))
    scheduler.start()

    wake_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def on_wake():
        loop.call_soon_threadsafe(wake_event.set)

    listener = WakeWordListener(on_wake=on_wake)
    listener.start()

    print("\n" + "=" * 68)
    print("  ⚡ JARVIS AUTONOMOUS HANDS-FREE MODE (MARK VII) ACTIVE")
    print("  🎙️  Passive Listener: 'Hey JARVIS' (openWakeWord Neural Model)")
    print("  🔊  Vocal Feedback: Kokoro-82M (24kHz British Accent)")
    print("  ⏰  Proactive Reminders & Desktop Toast Alerts: Enabled")
    print("  Press Ctrl+C at any time to power down.")
    print("=" * 68 + "\n")

    greeting = "All autonomous subsystems online. Awaiting your wake command, sir."
    print(f"JARVIS: {greeting}\n")
    await tts.speak_text(greeting)

    try:
        while True:
            print("[👂 Listening for 'Hey JARVIS' in background...]")
            await wake_event.wait()
            wake_event.clear()

            print("\n[⚡ WAKE-WORD DETECTED: 'Hey JARVIS']")
            print("[🎤 Microphone active - Speak now... (auto-stops on silence)]")

            audio = await asyncio.to_thread(recorder.record_until_silence, 9.0)
            if len(audio) == 0:
                print("[No voice captured.]\n")
                continue

            print("[⚡ Transcribing speech with Whisper...]")
            transcribed = await asyncio.to_thread(stt.transcribe, audio)
            if not transcribed:
                print("[Speech could not be parsed.]\n")
                continue

            print(f"User (Spoken) > {transcribed}\n")
            print("JARVIS > ", end="", flush=True)

            try:
                await tts.stream_and_speak(
                    agent.stream_chat(transcribed),
                    on_token=lambda chunk: print(chunk, end="", flush=True),
                )
            except Exception as e:
                print(f"[Neural error: {e}]")
            print("\n")
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\nJARVIS: Powering down autonomous listener. Have a pleasant day, sir.\n")
    finally:
        listener.stop()
        scheduler.stop()


def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomous AI Assistant")
    parser.add_argument("--query", "-q", type=str, help="Execute a single one-shot query and exit")
    parser.add_argument("--status", "-s", action="store_true", help="Print system telemetry and exit")
    parser.add_argument("--voice", "-v", action="store_true", help="Enable spoken voice output")
    parser.add_argument("--hud", action="store_true", help="Launch the Futuristic Sci-Fi Holographic Web HUD")
    parser.add_argument("--wake-word", "--hands-free", action="store_true", help="Continuous hands-free wake word detection ('Hey JARVIS')")
    parser.add_argument("--port", type=int, default=8000, help="Web server port for the HUD (default: 8000)")
    args = parser.parse_args()

    agent = JarvisAgent()

    if args.hud:
        from jarvis.server.app import start_server
        import webbrowser
        import threading
        url = f"http://127.0.0.1:{args.port}"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        start_server(port=args.port, agent=agent)
        return

    if args.wake_word:
        asyncio.run(autonomous_wake_word_loop(agent))
        return

    if args.status:
        print_system_info(agent, voice_enabled=args.voice)
        return

    if args.query:
        asyncio.run(one_shot_query(agent, args.query, voice_enabled=args.voice))
        return

    asyncio.run(interactive_loop(agent, voice_enabled=args.voice))


if __name__ == "__main__":
    main()

