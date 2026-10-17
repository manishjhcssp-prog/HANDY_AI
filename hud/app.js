/**
 * JARVIS AI MARK VII - HOLOGRAPHIC HUD CONTROLLER
 * WebSocket synchronization, Audio Reactive Arc Reactor Canvas,
 * Telemetry radial gauges, and real-time dialogue streaming.
 */

(function () {
    'use strict';

    // State Variables
    let ws = null;
    let wsConnected = false;
    let voiceFeedbackActive = true;
    let currentAgentTurnBubble = null;
    let pingStartTime = 0;
    let currentState = 'idle'; // 'idle' | 'listening' | 'transcribing' | 'thinking' | 'speaking'

    // DOM Elements
    const statusTextEl = document.getElementById('hud-status-text');
    const statusPillEl = document.getElementById('hud-connection-status');
    const latencyValEl = document.getElementById('hud-latency-val');
    const uptimeValEl = document.getElementById('hud-uptime-val');
    const voiceToggleBtn = document.getElementById('btn-toggle-voice');
    const voiceToggleLabel = document.getElementById('voice-toggle-label');
    const resetMemoryBtn = document.getElementById('btn-reset-memory');

    // Telemetry Elements
    const cpuBarEl = document.getElementById('cpu-gauge-bar');
    const cpuValEl = document.getElementById('cpu-percent-val');
    const ramBarEl = document.getElementById('ram-gauge-bar');
    const ramValEl = document.getElementById('ram-percent-val');
    const ramSubEl = document.getElementById('ram-gb-sub');
    const diskMetricVal = document.getElementById('disk-metric-val');
    const diskProgressBar = document.getElementById('disk-progress-bar');
    const batteryMetricVal = document.getElementById('battery-metric-val');
    const batteryProgressBar = document.getElementById('battery-progress-bar');
    const routerProviderVal = document.getElementById('router-provider-val');
    const routerModelVal = document.getElementById('router-model-val');
    const routerKeyVal = document.getElementById('router-key-val');
    const routerCostVal = document.getElementById('router-cost-val');
    const keyPoolList = document.getElementById('key-pool-list');

    // Reactor Overlay & Voice Controls
    const headlineEl = document.getElementById('reactor-status-headline');
    const sublineEl = document.getElementById('reactor-status-sub');
    const heroMicBtn = document.getElementById('hero-mic-btn');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessagesEl = document.getElementById('chat-messages');
    const terminalStreamEl = document.getElementById('terminal-stream');

    // Tab buttons
    const tabDialogueBtn = document.getElementById('tab-dialogue');
    const tabTerminalBtn = document.getElementById('tab-terminal');
    const viewDialogue = document.getElementById('view-dialogue');
    const viewTerminal = document.getElementById('view-terminal');

    // ==========================================================================
    // 1. WEBSOCKET CLIENT & EVENT DISPATCH
    // ==========================================================================
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host || '127.0.0.1:8000';
        const wsUrl = `${protocol}//${host}/ws`;

        updateStatus('ESTABLISHING LINK...', false);

        try {
            ws = new WebSocket(wsUrl);
        } catch (err) {
            console.error('WebSocket creation error:', err);
            scheduleReconnect();
            return;
        }

        ws.onopen = function () {
            wsConnected = true;
            updateStatus('ONLINE // NEURAL LINK ACTIVE', true);
            appendLog('INFO', 'WebSocket bridge established with JARVIS core.');
            measurePing();
        };

        ws.onmessage = function (event) {
            try {
                const packet = JSON.parse(event.data);
                handleIncomingPacket(packet);
            } catch (e) {
                console.error('Failed to parse incoming WS packet:', e);
            }
        };

        ws.onclose = function () {
            wsConnected = false;
            updateStatus('OFFLINE // LINK SEVERED', false);
            appendLog('WARN', 'Quantum link lost. Attempting reconnection...');
            scheduleReconnect();
        };

        ws.onerror = function (err) {
            console.warn('WebSocket connection notice:', err);
        };
    }

    function scheduleReconnect() {
        setTimeout(function () {
            if (!wsConnected) {
                connectWebSocket();
            }
        }, 2500);
    }

    function updateStatus(text, isOnline) {
        if (statusTextEl) statusTextEl.textContent = text;
        if (statusPillEl) {
            if (isOnline) {
                statusPillEl.style.borderColor = 'var(--neon-cyan)';
                statusPillEl.style.background = 'rgba(0, 240, 255, 0.08)';
            } else {
                statusPillEl.style.borderColor = 'var(--neon-crimson)';
                statusPillEl.style.background = 'rgba(255, 0, 85, 0.1)';
            }
        }
    }

    function measurePing() {
        if (wsConnected && ws.readyState === WebSocket.OPEN) {
            pingStartTime = performance.now();
            // Ping simulated via telemetry heartbeat
        }
    }

    function sendPacket(data) {
        if (wsConnected && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        } else {
            appendLog('ERROR', 'Directive failed: Neural link is offline.');
        }
    }

    // ==========================================================================
    // 2. PACKET HANDLERS
    // ==========================================================================
    function handleIncomingPacket(packet) {
        switch (packet.type) {
            case 'connected':
                appendLog('INFO', packet.message);
                break;

            case 'telemetry':
                renderTelemetry(packet.data);
                // Compute round-trip ping if active
                if (pingStartTime > 0) {
                    const elapsed = Math.round(performance.now() - pingStartTime);
                    if (latencyValEl) latencyValEl.textContent = `${elapsed} ms`;
                    pingStartTime = 0;
                }
                break;

            case 'agent_state':
                setAgentState(packet.state);
                break;

            case 'user_message':
                appendUserMessage(packet.message);
                break;

            case 'agent_chunk':
                appendAgentChunk(packet.token);
                break;

            case 'agent_done':
                finalizeAgentTurn(packet.full_text);
                break;

            case 'log':
                appendLog(packet.level, packet.message);
                break;

            case 'history_cleared':
                chatMessagesEl.innerHTML = '';
                appendWelcomeTurn();
                appendLog('WARN', 'Conversational memory reset.');
                break;

            default:
                break;
        }
    }

    function setAgentState(state) {
        currentState = state;
        switch (state) {
            case 'listening':
                headlineEl.textContent = 'LISTENING...';
                sublineEl.textContent = 'Microphone matrix active';
                heroMicBtn.classList.add('active');
                break;
            case 'transcribing':
                headlineEl.textContent = 'TRANSCRIBING...';
                sublineEl.textContent = 'Acoustic waveform processing';
                heroMicBtn.classList.add('active');
                break;
            case 'thinking':
                headlineEl.textContent = 'ANALYZING INTENT...';
                sublineEl.textContent = 'Executing neural routing & tools';
                heroMicBtn.classList.remove('active');
                break;
            case 'speaking':
                headlineEl.textContent = 'VOCALIZING RESPONSE';
                sublineEl.textContent = 'Kokoro Neural TTS streaming';
                heroMicBtn.classList.remove('active');
                break;
            case 'idle':
            default:
                headlineEl.textContent = 'SYSTEM STANDBY';
                sublineEl.textContent = 'Listening for user directives';
                heroMicBtn.classList.remove('active');
                break;
        }
    }

    // ==========================================================================
    // 3. TELEMETRY RENDERER
    // ==========================================================================
    function renderTelemetry(data) {
        // Circumference for r=42 is ~264
        const CIRCUMFERENCE = 264;

        // CPU
        const cpu = Math.round(data.cpu_percent || 0);
        if (cpuValEl) cpuValEl.textContent = `${cpu}%`;
        if (cpuBarEl) {
            const offset = CIRCUMFERENCE - (cpu / 100) * CIRCUMFERENCE;
            cpuBarEl.style.strokeDashoffset = offset;
        }

        // RAM
        const ram = Math.round(data.ram_percent || 0);
        const ramUsed = (data.ram_used_gb || 0).toFixed(1);
        const ramTotal = (data.ram_total_gb || 0).toFixed(1);
        if (ramValEl) ramValEl.textContent = `${ram}%`;
        if (ramSubEl) ramSubEl.textContent = `${ramUsed}/${ramTotal} GB`;
        if (ramBarEl) {
            const offset = CIRCUMFERENCE - (ram / 100) * CIRCUMFERENCE;
            ramBarEl.style.strokeDashoffset = offset;
        }

        // Disk
        const disk = Math.round(data.disk_percent || 0);
        const diskFree = (data.disk_free_gb || 0).toFixed(0);
        if (diskMetricVal) diskMetricVal.textContent = `${disk}% (${diskFree} GB free)`;
        if (diskProgressBar) diskProgressBar.style.width = `${disk}%`;

        // Battery
        const batt = data.battery || {};
        if (batt.percent !== undefined && batt.percent !== null) {
            const plugged = batt.power_plugged ? 'AC Plugged' : 'On Battery';
            if (batteryMetricVal) batteryMetricVal.textContent = `${batt.percent}% (${plugged})`;
            if (batteryProgressBar) batteryProgressBar.style.width = `${batt.percent}%`;
        } else {
            if (batteryMetricVal) batteryMetricVal.textContent = 'AC Powered (Desktop)';
            if (batteryProgressBar) batteryProgressBar.style.width = '100%';
        }

        // Uptime
        if (data.uptime_seconds !== undefined && uptimeValEl) {
            const hrs = String(Math.floor(data.uptime_seconds / 3600)).padStart(2, '0');
            const mins = String(Math.floor((data.uptime_seconds % 3600) / 60)).padStart(2, '0');
            const secs = String(data.uptime_seconds % 60).padStart(2, '0');
            uptimeValEl.textContent = `${hrs}:${mins}:${secs}`;
        }

        // Router Details
        if (routerProviderVal) routerProviderVal.textContent = (data.active_provider || 'Groq').toUpperCase();
        if (routerModelVal) routerModelVal.textContent = data.active_model || 'Local Tool Controller';
        if (routerKeyVal) routerKeyVal.textContent = data.active_key || 'Local System';

        // Key Pools
        if (data.key_pools && keyPoolList) {
            keyPoolList.innerHTML = '';
            for (const [provider, pool] of Object.entries(data.key_pools)) {
                const total = pool.total_keys || 0;
                const avail = pool.available_keys || 0;
                const item = document.createElement('div');
                item.className = 'pool-item';
                item.innerHTML = `<span class="name">${provider.toUpperCase()}</span><span class="stat">${avail}/${total} Active</span>`;
                keyPoolList.appendChild(item);
            }
        }
    }

    // ==========================================================================
    // 4. CHAT DIALOGUE & LOGS
    // ==========================================================================
    function appendWelcomeTurn() {
        const turn = document.createElement('div');
        turn.className = 'chat-turn assistant-turn';
        turn.innerHTML = `
            <div class="avatar-badge">J</div>
            <div class="turn-bubble">
                <div class="turn-header">
                    <span class="turn-sender">JARVIS</span>
                    <span class="turn-time">LIVE</span>
                </div>
                <div class="turn-text">Good day, sir. All neural subsystems, workstation controllers, and the holographic HUD are at your service. How may I assist you today?</div>
            </div>
        `;
        chatMessagesEl.appendChild(turn);
    }

    function appendUserMessage(text) {
        const turn = document.createElement('div');
        turn.className = 'chat-turn user-turn';
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        turn.innerHTML = `
            <div class="avatar-badge">U</div>
            <div class="turn-bubble">
                <div class="turn-header">
                    <span class="turn-sender">USER</span>
                    <span class="turn-time">${now}</span>
                </div>
                <div class="turn-text">${escapeHtml(text)}</div>
            </div>
        `;
        chatMessagesEl.appendChild(turn);
        scrollChatToBottom();
    }

    function appendAgentChunk(token) {
        if (!currentAgentTurnBubble) {
            const turn = document.createElement('div');
            turn.className = 'chat-turn assistant-turn';
            const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            turn.innerHTML = `
                <div class="avatar-badge">J</div>
                <div class="turn-bubble">
                    <div class="turn-header">
                        <span class="turn-sender">JARVIS</span>
                        <span class="turn-time">${now}</span>
                    </div>
                    <div class="turn-text"></div>
                </div>
            `;
            chatMessagesEl.appendChild(turn);
            currentAgentTurnBubble = turn.querySelector('.turn-text');
        }
        currentAgentTurnBubble.textContent += token;
        scrollChatToBottom();
    }

    function finalizeAgentTurn(fullText) {
        if (currentAgentTurnBubble && fullText) {
            currentAgentTurnBubble.textContent = fullText;
        }
        currentAgentTurnBubble = null;
        scrollChatToBottom();
    }

    function appendLog(level, message) {
        const now = new Date().toLocaleTimeString();
        const logLine = document.createElement('div');
        logLine.className = `log-line log-${level.toLowerCase()}`;
        logLine.innerHTML = `<span class="log-ts">[${now}]</span> [${level}] ${escapeHtml(message)}`;
        terminalStreamEl.appendChild(logLine);
        terminalStreamEl.scrollTop = terminalStreamEl.scrollHeight;
    }

    function scrollChatToBottom() {
        const viewport = document.getElementById('view-dialogue');
        if (viewport) {
            viewport.scrollTop = viewport.scrollHeight;
        }
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // ==========================================================================
    // 5. ARC REACTOR CANVAS ENGINE (Interactive 60fps Sci-Fi Graphics)
    // ==========================================================================
    const canvas = document.getElementById('arc-reactor-canvas');
    const ctx = canvas.getContext('2d');

    // Particle Array
    const particles = [];
    const NUM_PARTICLES = 36;
    for (let i = 0; i < NUM_PARTICLES; i++) {
        particles.push({
            angle: Math.random() * Math.PI * 2,
            distance: 80 + Math.random() * 150,
            speed: 0.005 + Math.random() * 0.015,
            size: 1 + Math.random() * 2,
            opacity: 0.3 + Math.random() * 0.7,
        });
    }

    let ringAngle1 = 0;
    let ringAngle2 = 0;
    let ringAngle3 = 0;
    let corePulse = 0;

    function renderArcReactor() {
        const width = canvas.width;
        const height = canvas.height;
        const cx = width / 2;
        const cy = height / 2;

        ctx.clearRect(0, 0, width, height);

        // Dynamic speed multiplier based on agent state
        let speedMult = 1.0;
        let coreColor = '#00f0ff';
        let glowColor = 'rgba(0, 240, 255, ';

        if (currentState === 'thinking') {
            speedMult = 2.8;
            coreColor = '#ffb700';
            glowColor = 'rgba(255, 183, 0, ';
        } else if (currentState === 'listening') {
            speedMult = 1.8;
            coreColor = '#ff0055';
            glowColor = 'rgba(255, 0, 85, ';
        } else if (currentState === 'speaking') {
            speedMult = 1.4;
            coreColor = '#38bdf8';
            glowColor = 'rgba(56, 189, 248, ';
        }

        ringAngle1 += 0.008 * speedMult;
        ringAngle2 -= 0.012 * speedMult;
        ringAngle3 += 0.004 * speedMult;
        corePulse += 0.04 * speedMult;

        const pulseScale = 1 + Math.sin(corePulse) * 0.08;

        // 1. Ambient Background Glow
        const bgGlow = ctx.createRadialGradient(cx, cy, 10, cx, cy, 220);
        bgGlow.addColorStop(0, glowColor + '0.22)');
        bgGlow.addColorStop(0.5, glowColor + '0.06)');
        bgGlow.addColorStop(1, 'transparent');
        ctx.fillStyle = bgGlow;
        ctx.beginPath();
        ctx.arc(cx, cy, 220, 0, Math.PI * 2);
        ctx.fill();

        // 2. Outer Segmented Resonator Ring (Radius 210)
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringAngle3);
        ctx.strokeStyle = glowColor + '0.35)';
        ctx.lineWidth = 2;
        ctx.setLineDash([12, 8, 3, 8]);
        ctx.beginPath();
        ctx.arc(0, 0, 210, 0, Math.PI * 2);
        ctx.stroke();

        // Outer Tick Marks
        ctx.setLineDash([]);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = glowColor + '0.5)';
        const numTicks = 48;
        for (let i = 0; i < numTicks; i++) {
            const a = (i / numTicks) * Math.PI * 2;
            const r1 = i % 4 === 0 ? 200 : 205;
            const r2 = 210;
            ctx.beginPath();
            ctx.moveTo(Math.cos(a) * r1, Math.sin(a) * r1);
            ctx.lineTo(Math.cos(a) * r2, Math.sin(a) * r2);
            ctx.stroke();
        }
        ctx.restore();

        // 3. Middle Counter-Rotating Ring (Radius 165)
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringAngle2);
        ctx.strokeStyle = glowColor + '0.6)';
        ctx.lineWidth = 3;
        ctx.setLineDash([25, 12, 10, 12]);
        ctx.beginPath();
        ctx.arc(0, 0, 165, 0, Math.PI * 2);
        ctx.stroke();

        // Small Node Nodes
        ctx.setLineDash([]);
        for (let i = 0; i < 8; i++) {
            const a = (i / 8) * Math.PI * 2;
            ctx.fillStyle = coreColor;
            ctx.beginPath();
            ctx.arc(Math.cos(a) * 165, Math.sin(a) * 165, 3.5, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();

        // 4. Ten Magnetic Energy Conduits / Coils (Radius 115)
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringAngle1);
        const NUM_COILS = 10;
        for (let i = 0; i < NUM_COILS; i++) {
            const a = (i / NUM_COILS) * Math.PI * 2;
            const coilX = Math.cos(a) * 115;
            const coilY = Math.sin(a) * 115;

            // Copper Conduit Box
            ctx.save();
            ctx.translate(coilX, coilY);
            ctx.rotate(a + Math.PI / 2);

            ctx.fillStyle = 'rgba(12, 22, 38, 0.95)';
            ctx.strokeStyle = coreColor;
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            ctx.rect(-14, -8, 28, 16);
            ctx.fill();
            ctx.stroke();

            // Inner glowing core segment
            ctx.fillStyle = glowColor + '0.7)';
            ctx.fillRect(-10, -5, 20, 10);
            ctx.restore();
        }
        ctx.restore();

        // 5. Inner Resonator Ring (Radius 75)
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(ringAngle2 * 1.5);
        ctx.strokeStyle = coreColor;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(0, 0, 75, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();

        // 6. Central Plasma Energy Core
        const coreR = 48 * pulseScale;
        const plasmaGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, coreR);
        plasmaGrad.addColorStop(0, '#ffffff');
        plasmaGrad.addColorStop(0.3, coreColor);
        plasmaGrad.addColorStop(0.7, glowColor + '0.6)');
        plasmaGrad.addColorStop(1, 'transparent');

        ctx.fillStyle = plasmaGrad;
        ctx.beginPath();
        ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
        ctx.fill();

        // Inner triangular power glyph
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-ringAngle1 * 2);
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 2.5;
        ctx.shadowColor = coreColor;
        ctx.shadowBlur = 12;
        ctx.beginPath();
        const triR = 24 * pulseScale;
        for (let i = 0; i < 3; i++) {
            const a = (i / 3) * Math.PI * 2 - Math.PI / 2;
            const x = Math.cos(a) * triR;
            const y = Math.sin(a) * triR;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
        ctx.restore();

        // 7. Ambient Inward-Floating Particles
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            p.distance -= 0.35 * speedMult;
            p.angle += p.speed * speedMult;
            if (p.distance < 45) {
                p.distance = 200 + Math.random() * 40;
            }

            const px = cx + Math.cos(p.angle) * p.distance;
            const py = cy + Math.sin(p.angle) * p.distance;

            ctx.fillStyle = glowColor + p.opacity + ')';
            ctx.beginPath();
            ctx.arc(px, py, p.size, 0, Math.PI * 2);
            ctx.fill();
        }

        requestAnimationFrame(renderArcReactor);
    }

    // ==========================================================================
    // 6. EVENT LISTENERS & INTERACTION
    // ==========================================================================
    function setupInteractions() {
        // Chat Form Submit
        if (chatForm) {
            chatForm.addEventListener('submit', function (e) {
                e.preventDefault();
                const msg = chatInput.value.trim();
                if (!msg) return;

                sendPacket({
                    type: 'chat',
                    message: msg,
                    voice: voiceFeedbackActive,
                });
                chatInput.value = '';
            });
        }

        // Hero Microphone Button
        if (heroMicBtn) {
            heroMicBtn.addEventListener('click', function () {
                sendPacket({ type: 'voice_trigger' });
            });
        }

        // Voice Toggle Button
        if (voiceToggleBtn) {
            voiceToggleBtn.addEventListener('click', function () {
                voiceFeedbackActive = !voiceFeedbackActive;
                voiceToggleLabel.textContent = voiceFeedbackActive ? 'VOICE: ON' : 'VOICE: OFF';
                voiceToggleBtn.style.borderColor = voiceFeedbackActive ? 'var(--neon-cyan)' : 'var(--text-muted)';
                appendLog('INFO', `Spoken vocal audio feedback set to: ${voiceFeedbackActive ? 'ENABLED' : 'DISABLED'}`);
            });
        }

        // Reset Matrix Button
        if (resetMemoryBtn) {
            resetMemoryBtn.addEventListener('click', function () {
                if (confirm('Reset conversational matrix back to initial state?')) {
                    sendPacket({ type: 'reset' });
                }
            });
        }

        // Quick Directive Pills
        document.querySelectorAll('.quick-pill').forEach(function (pill) {
            pill.addEventListener('click', function () {
                const prompt = pill.getAttribute('data-prompt');
                if (prompt) {
                    sendPacket({
                        type: 'chat',
                        message: prompt,
                        voice: voiceFeedbackActive,
                    });
                }
            });
        });

        // Tab Switching
        if (tabDialogueBtn && tabTerminalBtn) {
            tabDialogueBtn.addEventListener('click', function () {
                tabDialogueBtn.classList.add('active');
                tabTerminalBtn.classList.remove('active');
                viewDialogue.classList.add('active-view');
                viewTerminal.classList.remove('active-view');
            });

            tabTerminalBtn.addEventListener('click', function () {
                tabTerminalBtn.classList.add('active');
                tabDialogueBtn.classList.remove('active');
                viewTerminal.classList.add('active-view');
                viewDialogue.classList.remove('active-view');
            });
        }
    }

    // Initialize HUD on DOM Load
    window.addEventListener('DOMContentLoaded', function () {
        setupInteractions();
        connectWebSocket();
        renderArcReactor();
    });

})();
