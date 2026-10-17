"""
JARVIS AI - Backend FastAPI & WebSocket Server (Tier 4)
Bridges the JARVIS cognitive core, audio pipeline, and OS tools
to the Futuristic Sci-Fi Holographic HUD with real-time state synchronization.
"""

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis.brain.agent import JarvisAgent
from jarvis.tools.sys_info import get_system_summary
from jarvis.audio.tts import TTSEngine
from jarvis.audio.stt import STTEngine
from jarvis.audio.recorder import AudioRecorder

logger = logging.getLogger("JARVIS.Server")

HUD_DIR = Path(__file__).resolve().parent.parent.parent / "hud"


class ChatRequest(BaseModel):
    message: str
    voice: bool = False


class ConnectionManager:
    """Manages active WebSocket connections and telemetry broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"HUD WebSocket client connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"HUD WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts a JSON packet to all connected HUD clients."""
        if not self.active_connections:
            return
        dead_connections = set()
        payload = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.add(connection)
        for dead in dead_connections:
            self.active_connections.discard(dead)

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        """Sends a JSON packet to a specific WebSocket client."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Error sending message to client: {e}")


def create_app(agent: Optional[JarvisAgent] = None) -> FastAPI:
    """Factory creating configured FastAPI app for the JARVIS HUD."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("JARVIS HUD Core Server initializing...")
        app.state.telemetry_task = asyncio.create_task(telemetry_worker())
        logger.info("Telemetry broadcast loop running.")
        try:
            yield
        finally:
            logger.info("JARVIS HUD Server powering down...")
            if app.state.telemetry_task:
                app.state.telemetry_task.cancel()
                try:
                    await app.state.telemetry_task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="JARVIS Holographic HUD Server",
        description="Real-time WebSocket & REST bridge for JARVIS AI Mark VII",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for external local frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared Agent & Subsystems
    app.state.agent = agent or JarvisAgent()
    app.state.tts = TTSEngine()
    app.state.stt = None  # Lazy loaded on voice demand
    app.state.recorder = None
    app.state.manager = ConnectionManager()
    app.state.start_time = time.time()
    app.state.telemetry_task = None

    def get_stt() -> STTEngine:
        if app.state.stt is None:
            app.state.stt = STTEngine()
        return app.state.stt

    def get_recorder() -> AudioRecorder:
        if app.state.recorder is None:
            app.state.recorder = AudioRecorder()
        return app.state.recorder

    async def telemetry_worker():
        """Periodically pushes real-time system metrics to all HUD clients."""
        try:
            while True:
                await asyncio.sleep(1.5)
                if not app.state.manager.active_connections:
                    continue

                sys_info = await asyncio.to_thread(get_system_summary)
                agent_telemetry = app.state.agent.get_status()
                uptime_seconds = int(time.time() - app.state.start_time)

                telemetry_packet = {
                    "type": "telemetry",
                    "data": {
                        "cpu_percent": sys_info.get("cpu_percent", 0.0),
                        "ram_percent": sys_info.get("ram_percent", 0.0),
                        "ram_used_gb": sys_info.get("ram_used_gb", 0.0),
                        "ram_total_gb": sys_info.get("ram_total_gb", 0.0),
                        "disk_percent": sys_info.get("disk_percent", 0.0),
                        "disk_free_gb": sys_info.get("disk_free_gb", 0.0),
                        "battery": sys_info.get("battery", {}),
                        "uptime_seconds": uptime_seconds,
                        "active_provider": agent_telemetry.get("active_provider") or "Standby",
                        "active_model": agent_telemetry.get("active_model") or "Local Router",
                        "active_key": agent_telemetry.get("active_key_masked") or "none",
                        "cost_protection": agent_telemetry.get("free_only_mode", True),
                        "key_pools": agent_telemetry.get("key_manager", {}),
                    },
                }
                await app.state.manager.broadcast(telemetry_packet)
        except (asyncio.CancelledError, GeneratorExit):
            pass
        except Exception as e:
            logger.debug(f"Telemetry broadcast notice: {e}")

    # --- REST Endpoints ---

    @app.get("/api/status")
    async def get_status():
        telemetry = app.state.agent.get_status()
        return {
            "status": "online",
            "name": "JARVIS Mark VII",
            "uptime_seconds": int(time.time() - app.state.start_time),
            "telemetry": telemetry,
        }

    @app.get("/api/telemetry")
    async def get_telemetry():
        sys_info = await asyncio.to_thread(get_system_summary)
        return sys_info

    @app.get("/api/history")
    async def get_history():
        return {"history": app.state.agent.get_history()}

    @app.post("/api/reset")
    async def reset_memory():
        app.state.agent.reset()
        await app.state.manager.broadcast({
            "type": "log",
            "level": "WARN",
            "message": "Conversational memory reset to initial system matrix."
        })
        return {"status": "success", "message": "Memory matrix reinitialized, sir."}

    @app.post("/api/chat")
    async def rest_chat(req: ChatRequest):
        try:
            resp = await app.state.agent.chat(req.message)
            if req.voice:
                asyncio.create_task(app.state.tts.speak_text(resp.content))
            return {
                "content": resp.content,
                "model": resp.model,
                "provider": resp.provider,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- WebSocket Endpoint ---

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await app.state.manager.connect(websocket)

        # Send initial welcome and status packet
        await app.state.manager.send_personal(websocket, {
            "type": "connected",
            "message": "Quantum link established. JARVIS Mark VII HUD online, sir.",
            "timestamp": time.time(),
        })

        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                except Exception:
                    continue

                msg_type = payload.get("type")

                # Handle Text / Voice Chat Message
                if msg_type == "chat":
                    user_message = payload.get("message", "").strip()
                    voice_enabled = payload.get("voice", False)
                    if not user_message:
                        continue

                    # Broadcast user turn
                    await app.state.manager.broadcast({
                        "type": "user_message",
                        "message": user_message,
                        "timestamp": time.time(),
                    })

                    # Broadcast state: THINKING
                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "thinking",
                    })

                    await app.state.manager.broadcast({
                        "type": "log",
                        "level": "INFO",
                        "message": f"Processing directive: '{user_message}'",
                    })

                    full_response = []

                    # Stream tokens in real-time
                    try:
                        async for token in app.state.agent.stream_chat(user_message):
                            full_response.append(token)
                            await app.state.manager.broadcast({
                                "type": "agent_chunk",
                                "token": token,
                            })
                    except Exception as err:
                        error_msg = f"Neural pathway error: {str(err)}"
                        full_response.append(error_msg)
                        await app.state.manager.broadcast({
                            "type": "agent_chunk",
                            "token": error_msg,
                        })

                    complete_text = "".join(full_response).strip()

                    # Finalize response
                    await app.state.manager.broadcast({
                        "type": "agent_done",
                        "full_text": complete_text,
                    })

                    # Voice synthesis if requested
                    if voice_enabled and complete_text:
                        await app.state.manager.broadcast({
                            "type": "agent_state",
                            "state": "speaking",
                        })
                        try:
                            await app.state.tts.speak_text(complete_text)
                        except Exception as e:
                            logger.warning(f"TTS vocalization error: {e}")

                    # Return to IDLE
                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "idle",
                    })

                # Handle Voice Trigger from HUD Microphone Button
                elif msg_type == "voice_trigger":
                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "listening",
                    })
                    await app.state.manager.broadcast({
                        "type": "log",
                        "level": "INFO",
                        "message": "Microphone matrix opened. Listening for user speech...",
                    })

                    recorder = get_recorder()
                    stt = get_stt()

                    # Record audio in thread
                    audio_data = await asyncio.to_thread(recorder.record_until_silence, 8.0)
                    if len(audio_data) == 0:
                        await app.state.manager.broadcast({
                            "type": "agent_state",
                            "state": "idle",
                        })
                        await app.state.manager.broadcast({
                            "type": "log",
                            "level": "WARN",
                            "message": "No voice audio detected on microphone.",
                        })
                        continue

                    # Transcribe
                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "transcribing",
                    })
                    await app.state.manager.broadcast({
                        "type": "log",
                        "level": "INFO",
                        "message": "Transcribing captured acoustic waveform with Whisper...",
                    })

                    transcribed = await asyncio.to_thread(stt.transcribe, audio_data)
                    if not transcribed:
                        await app.state.manager.broadcast({
                            "type": "agent_state",
                            "state": "idle",
                        })
                        await app.state.manager.broadcast({
                            "type": "log",
                            "level": "WARN",
                            "message": "Speech could not be parsed clearly.",
                        })
                        continue

                    # Successfully transcribed - now execute as chat message
                    await app.state.manager.broadcast({
                        "type": "transcription",
                        "text": transcribed,
                    })
                    await app.state.manager.broadcast({
                        "type": "user_message",
                        "message": transcribed,
                    })

                    # Process response
                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "thinking",
                    })
                    full_resp = []
                    async for token in app.state.agent.stream_chat(transcribed):
                        full_resp.append(token)
                        await app.state.manager.broadcast({
                            "type": "agent_chunk",
                            "token": token,
                        })

                    answer = "".join(full_resp).strip()
                    await app.state.manager.broadcast({
                        "type": "agent_done",
                        "full_text": answer,
                    })

                    # Vocalize back with Kokoro TTS
                    if answer:
                        await app.state.manager.broadcast({
                            "type": "agent_state",
                            "state": "speaking",
                        })
                        await app.state.tts.speak_text(answer)

                    await app.state.manager.broadcast({
                        "type": "agent_state",
                        "state": "idle",
                    })

                # Handle Reset
                elif msg_type == "reset":
                    app.state.agent.reset()
                    await app.state.manager.broadcast({
                        "type": "history_cleared",
                    })
                    await app.state.manager.broadcast({
                        "type": "log",
                        "level": "WARN",
                        "message": "Conversational memory reset to initial system matrix.",
                    })

        except WebSocketDisconnect:
            app.state.manager.disconnect(websocket)
        except Exception as e:
            logger.warning(f"WebSocket session terminated: {e}")
            app.state.manager.disconnect(websocket)

    # --- Serve Frontend HUD ---
    if HUD_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(HUD_DIR)), name="static")

        @app.get("/")
        async def serve_hud():
            index_file = HUD_DIR / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return JSONResponse({"status": "HUD frontend under construction"})

    return app


# Default singleton instance for uvicorn run
app = create_app()


def start_server(host: str = "127.0.0.1", port: int = 8000, agent: Optional[JarvisAgent] = None):
    """Launches the Uvicorn web server."""
    import uvicorn
    custom_app = create_app(agent=agent)
    print(f"\n==================================================================")
    print(f"  ⚡ JARVIS AI MARK VII - HOLOGRAPHIC HUD SERVER ACTIVE")
    print(f"  🌐 URL: http://{host}:{port}")
    print(f"  📡 WebSocket: ws://{host}:{port}/ws")
    print(f"==================================================================\n")
    try:
        uvicorn.run(custom_app, host=host, port=port, log_level="warning")
    except (KeyboardInterrupt, SystemExit):
        print("\nJARVIS HUD Server shut down cleanly, sir.\n")


if __name__ == "__main__":
    start_server()
