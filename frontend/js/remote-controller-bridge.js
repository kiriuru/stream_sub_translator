(function () {
  const workerUrlInput = document.getElementById("worker-url");
  const sessionIdInput = document.getElementById("session-id");
  const pairCodeInput = document.getElementById("pair-code");
  const micSelect = document.getElementById("mic-select");
  const refreshMicsBtn = document.getElementById("refresh-mics-btn");
  const connectBtn = document.getElementById("connect-btn");
  const stopBtn = document.getElementById("stop-btn");
  const statusLine = document.getElementById("status-line");
  const logBox = document.getElementById("log-box");

  const STORE_KEYS = {
    workerUrl: "sst.remote.bridge.worker_url",
    sessionId: "sst.remote.bridge.session_id",
    pairCode: "sst.remote.bridge.pair_code",
    micId: "sst.remote.bridge.mic_id",
  };
  const RECONNECT_BASE_MS = 1000;
  const RECONNECT_MAX_MS = 30000;
  const ICE_SERVERS = [
    { urls: "stun:stun.cloudflare.com:3478" },
    { urls: "stun:stun.l.google.com:19302" },
  ];
  const WEBRTC_USE_RAW_MIC_TRACK = true;
  const DIRECT_PCM_FALLBACK_ENABLED = false;
  const WEBRTC_AUDIO_SENDER_TUNING_ENABLED = false;
  const WEBRTC_AUDIO_SDP_TUNING_ENABLED = false;
  const WEBRTC_AUDIO_MAX_BITRATE_BPS = 128000;
  const WEBRTC_AUDIO_DISABLE_DTX = true;
  const WEBRTC_AUDIO_ENABLE_FEC = true;
  const WEBRTC_AUDIO_FORCE_CBR = true;
  const WEBRTC_AUDIO_PTIME_MS = 20;
  const VERBOSE_LOGS = (() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const debugParam = String(params.get("debug") || params.get("verbose") || "").trim().toLowerCase();
      if (debugParam === "1" || debugParam === "true" || debugParam === "yes" || debugParam === "on") {
        return true;
      }
      const persisted = String(localStorage.getItem("sst.remote.verbose_logs") || "").trim().toLowerCase();
      return persisted === "1" || persisted === "true" || persisted === "yes" || persisted === "on";
    } catch (_error) {
      return false;
    }
  })();

  const state = {
    signalingWs: null,
    remoteEventsWs: null,
    localIngestWs: null,
    pc: null,
    heartbeatTimer: null,
    localStream: null,
    running: false,
    micPermissionPrimed: false,
    manualStop: true,
    isClosing: false,
    reconnectTimer: null,
    reconnectAttempt: 0,
    fatalPairingError: false,
    micMonitorContext: null,
    micMonitorSource: null,
    micMonitorProcessor: null,
    micMonitorSink: null,
    micRmsWindowStartedAt: 0,
    micRmsAccumulator: 0,
    micRmsSamples: 0,
    outboundAudioContext: null,
    outboundAudioSource: null,
    outboundAudioGain: null,
    outboundAudioDestination: null,
    outboundWebRtcStream: null,
    outboundStatsTimer: null,
    outboundLastBytesSent: 0,
    outboundLastPacketsSent: 0,
    directIngestWs: null,
    directPcmContext: null,
    directPcmSource: null,
    directPcmProcessor: null,
    directPcmSink: null,
    directPcmWindowStartedAt: 0,
    directPcmChunksSent: 0,
    directPcmBytesSent: 0,
    directPcmRmsAccumulator: 0,
    directPcmRmsSamples: 0,
    directPcmChunksDropped: 0,
  };

  function log(message) {
    if (!logBox) return;
    const text = String(message || "");
    if (!VERBOSE_LOGS && isNoisyLogMessage(text)) {
      return;
    }
    logBox.textContent += `\n${new Date().toISOString()} ${text}`;
    logBox.scrollTop = logBox.scrollHeight;
  }

  function isNoisyLogMessage(message) {
    const text = String(message || "");
    if (!text) return false;
    return (
      text.startsWith("mic rms avg=") ||
      text.startsWith("direct pcm tx:") ||
      text.startsWith("outbound audio:") ||
      text.startsWith("local candidate=") ||
      text.startsWith("remote candidate=") ||
      text.startsWith("warning: Remote peer is not connected yet.")
    );
  }

  function setStatus(message, level) {
    if (!statusLine) return;
    statusLine.classList.remove("ok", "warn", "bad");
    if (level) {
      statusLine.classList.add(level);
    }
    statusLine.textContent = message;
  }

  function parseQuery() {
    const params = new URLSearchParams(window.location.search);
    return {
      workerUrl: String(params.get("worker_url") || "").trim(),
      sessionId: String(params.get("session_id") || "").trim(),
      pairCode: String(params.get("pair_code") || "").trim(),
      micId: String(params.get("mic_id") || "").trim(),
    };
  }

  function loadPersistedValues() {
    try {
      workerUrlInput.value = localStorage.getItem(STORE_KEYS.workerUrl) || workerUrlInput.value || "";
      sessionIdInput.value = localStorage.getItem(STORE_KEYS.sessionId) || sessionIdInput.value || "";
      pairCodeInput.value = localStorage.getItem(STORE_KEYS.pairCode) || pairCodeInput.value || "";
    } catch (_error) {
      // ignore localStorage failures
    }
  }

  function persistValues() {
    try {
      localStorage.setItem(STORE_KEYS.workerUrl, String(workerUrlInput?.value || "").trim());
      localStorage.setItem(STORE_KEYS.sessionId, String(sessionIdInput?.value || "").trim());
      localStorage.setItem(STORE_KEYS.pairCode, String(pairCodeInput?.value || "").trim());
      if (micSelect) {
        localStorage.setItem(STORE_KEYS.micId, String(micSelect.value || "").trim());
      }
    } catch (_error) {
      // ignore localStorage failures
    }
  }

  function currentMicSelection() {
    if (!micSelect) return "";
    return String(micSelect.value || "").trim();
  }

  function stopTracks(stream) {
    if (!stream) return;
    stream.getTracks().forEach((track) => {
      try {
        track.stop();
      } catch (_error) {
        // no-op
      }
    });
  }

  function clearReconnectTimer() {
    if (state.reconnectTimer) {
      window.clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
  }

  function resetReconnectState() {
    clearReconnectTimer();
    state.reconnectAttempt = 0;
  }

  function reconnectDelayMs(nextAttempt) {
    const exp = Math.max(0, Math.min(6, Number(nextAttempt) - 1));
    return Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * Math.pow(2, exp));
  }

  function scheduleReconnect(reason) {
    if (state.manualStop || state.isClosing) {
      return;
    }
    if (state.fatalPairingError) {
      return;
    }
    if (state.reconnectTimer) {
      return;
    }
    const nextAttempt = state.reconnectAttempt + 1;
    const delayMs = reconnectDelayMs(nextAttempt);
    const delaySec = (delayMs / 1000).toFixed(1);
    setStatus(`Connection lost, reconnect in ${delaySec}s...`, "warn");
    log(`reconnect scheduled (${reason}) in ${delaySec}s`);
    state.reconnectTimer = window.setTimeout(() => {
      state.reconnectTimer = null;
      state.reconnectAttempt = nextAttempt;
      startBridge().catch((error) => {
        log(`reconnect attempt failed: ${error}`);
        scheduleReconnect(`reconnect attempt failed: ${error}`);
      });
    }, delayMs);
  }

  function updateMicOptions(devices, preferredId) {
    if (!micSelect) return;
    micSelect.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = "Default microphone";
    micSelect.appendChild(defaultOption);

    (Array.isArray(devices) ? devices : []).forEach((device, index) => {
      const option = document.createElement("option");
      option.value = String(device.deviceId || "");
      const label = String(device.label || "").trim() || `Microphone ${index + 1}`;
      option.textContent = label;
      micSelect.appendChild(option);
    });

    const normalizedPreferred = String(preferredId || "").trim();
    if (normalizedPreferred && Array.from(micSelect.options).some((item) => item.value === normalizedPreferred)) {
      micSelect.value = normalizedPreferred;
    } else {
      micSelect.value = "";
    }
    persistValues();
  }

  async function refreshMicrophones(requestPermission) {
    if (!navigator.mediaDevices || typeof navigator.mediaDevices.enumerateDevices !== "function") {
      if (micSelect) {
        micSelect.innerHTML = '<option value="">Browser audio devices are unavailable</option>';
        micSelect.value = "";
      }
      return;
    }

    if (requestPermission && typeof navigator.mediaDevices.getUserMedia === "function") {
      let probeStream = null;
      try {
        probeStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        state.micPermissionPrimed = true;
      } catch (error) {
        log(`microphone permission failed: ${error}`);
      } finally {
        stopTracks(probeStream);
      }
    }

    const persistedId = (() => {
      try {
        return String(localStorage.getItem(STORE_KEYS.micId) || "").trim();
      } catch (_error) {
        return "";
      }
    })();

    const currentId = currentMicSelection();
    const devices = await navigator.mediaDevices.enumerateDevices();
    const microphones = devices.filter((item) => String(item.kind || "").toLowerCase() === "audioinput");
    updateMicOptions(microphones, currentId || persistedId);
    log(`microphones detected: ${microphones.length}`);
  }

  function normalizeBaseUrl(raw) {
    const value = String(raw || "").trim();
    if (!value) return "";
    try {
      const parsed = new URL(value);
      if (!/^https?:$/i.test(parsed.protocol)) {
        return "";
      }
      parsed.pathname = "";
      parsed.search = "";
      parsed.hash = "";
      return parsed.toString().replace(/\/$/, "");
    } catch (_error) {
      return "";
    }
  }

  function wsUrlFromHttp(baseUrl, pathAndQuery) {
    const parsed = new URL(baseUrl);
    parsed.protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
    parsed.pathname = pathAndQuery.split("?")[0];
    parsed.search = pathAndQuery.includes("?") ? `?${pathAndQuery.split("?")[1]}` : "";
    return parsed.toString();
  }

  function currentWsOrigin() {
    const url = new URL(window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.hash = "";
    url.search = "";
    return `${url.protocol}//${url.host}`;
  }

  function sendSignal(payload) {
    if (!state.signalingWs || state.signalingWs.readyState !== WebSocket.OPEN) return;
    state.signalingWs.send(JSON.stringify({ type: "signal", payload }));
  }

  function frameRms(samples) {
    if (!samples || samples.length <= 0) return 0;
    let sum = 0;
    for (let i = 0; i < samples.length; i += 1) {
      const value = Number(samples[i]) || 0;
      sum += value * value;
    }
    return Math.sqrt(sum / samples.length);
  }

  function downsampleFloatToInt16(input, inputSampleRate, outputSampleRate) {
    if (!input || input.length === 0) {
      return new Int16Array(0);
    }
    const sourceRate = Number(inputSampleRate) || outputSampleRate;
    if (sourceRate <= 0 || outputSampleRate <= 0) {
      return new Int16Array(0);
    }
    if (sourceRate === outputSampleRate) {
      const out = new Int16Array(input.length);
      for (let i = 0; i < input.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, input[i]));
        out[i] = sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767);
      }
      return out;
    }

    const ratio = sourceRate / outputSampleRate;
    const outputLength = Math.max(1, Math.floor(input.length / ratio));
    const out = new Int16Array(outputLength);
    for (let i = 0; i < outputLength; i += 1) {
      const index = Math.min(input.length - 1, Math.floor(i * ratio));
      const sample = Math.max(-1, Math.min(1, input[index]));
      out[i] = sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767);
    }
    return out;
  }

  function resetMicRmsStats() {
    state.micRmsWindowStartedAt = performance.now();
    state.micRmsAccumulator = 0;
    state.micRmsSamples = 0;
  }

  function logMicRmsIfNeeded(force) {
    const now = performance.now();
    if (!force && now - state.micRmsWindowStartedAt < 2000) {
      return;
    }
    const avgRms = state.micRmsSamples > 0 ? state.micRmsAccumulator / state.micRmsSamples : 0;
    log(`mic rms avg=${avgRms.toFixed(4)} samples=${state.micRmsSamples}`);
    resetMicRmsStats();
  }

  async function stopMicMonitor() {
    if (state.micMonitorProcessor) {
      try {
        state.micMonitorProcessor.disconnect();
      } catch (_error) {
        // no-op
      }
      state.micMonitorProcessor.onaudioprocess = null;
      state.micMonitorProcessor = null;
    }
    if (state.micMonitorSource) {
      try {
        state.micMonitorSource.disconnect();
      } catch (_error) {
        // no-op
      }
      state.micMonitorSource = null;
    }
    if (state.micMonitorSink) {
      try {
        state.micMonitorSink.disconnect();
      } catch (_error) {
        // no-op
      }
      state.micMonitorSink = null;
    }
    if (state.micMonitorContext) {
      try {
        await state.micMonitorContext.close();
      } catch (_error) {
        // no-op
      }
      state.micMonitorContext = null;
    }
  }

  async function startMicMonitor(stream) {
    await stopMicMonitor();
    if (!stream) return;
    const context = new window.AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(2048, 1, 1);
    const sink = context.createGain();
    sink.gain.value = 0;
    resetMicRmsStats();
    processor.onaudioprocess = (event) => {
      const channelData = event.inputBuffer.getChannelData(0);
      state.micRmsAccumulator += frameRms(channelData);
      state.micRmsSamples += 1;
      logMicRmsIfNeeded(false);
    };
    source.connect(processor);
    processor.connect(sink);
    sink.connect(context.destination);
    state.micMonitorContext = context;
    state.micMonitorSource = source;
    state.micMonitorProcessor = processor;
    state.micMonitorSink = sink;
    log(`mic monitor active; audio context state=${context.state}`);
  }

  function stopOutboundStats() {
    if (state.outboundStatsTimer) {
      window.clearInterval(state.outboundStatsTimer);
      state.outboundStatsTimer = null;
    }
    state.outboundLastBytesSent = 0;
    state.outboundLastPacketsSent = 0;
  }

  function resetDirectPcmStats() {
    state.directPcmWindowStartedAt = performance.now();
    state.directPcmChunksSent = 0;
    state.directPcmBytesSent = 0;
    state.directPcmRmsAccumulator = 0;
    state.directPcmRmsSamples = 0;
    state.directPcmChunksDropped = 0;
  }

  function logDirectPcmStatsIfNeeded(force) {
    const now = performance.now();
    if (!force && now - state.directPcmWindowStartedAt < 2000) {
      return;
    }
    const seconds = Math.max(0.001, (now - state.directPcmWindowStartedAt) / 1000);
    const kbps = (state.directPcmBytesSent * 8) / 1000 / seconds;
    const avgRms = state.directPcmRmsSamples > 0 ? state.directPcmRmsAccumulator / state.directPcmRmsSamples : 0;
    const wsState = state.directIngestWs ? state.directIngestWs.readyState : WebSocket.CLOSED;
    log(
      `direct pcm tx: chunks=${state.directPcmChunksSent} dropped=${state.directPcmChunksDropped} bytes=${state.directPcmBytesSent} avg_rms=${avgRms.toFixed(
        4
      )} rate_kbps=${kbps.toFixed(1)} ws_state=${wsState}`
    );
    resetDirectPcmStats();
  }

  function startOutboundStats() {
    stopOutboundStats();
    if (!state.pc) return;
    state.outboundStatsTimer = window.setInterval(async () => {
      try {
        if (!state.pc) return;
        const report = await state.pc.getStats();
        let outboundAudio = null;
        let trackAudio = null;
        report.forEach((item) => {
          if (item && item.type === "outbound-rtp" && item.kind === "audio" && !item.isRemote) {
            outboundAudio = item;
          }
          if (item && item.type === "track" && item.kind === "audio" && item.remoteSource === false) {
            trackAudio = item;
          }
        });
        if (!outboundAudio) {
          return;
        }
        const bytesSent = Number(outboundAudio.bytesSent || 0);
        const packetsSent = Number(outboundAudio.packetsSent || 0);
        const deltaBytes = Math.max(0, bytesSent - state.outboundLastBytesSent);
        const deltaPackets = Math.max(0, packetsSent - state.outboundLastPacketsSent);
        state.outboundLastBytesSent = bytesSent;
        state.outboundLastPacketsSent = packetsSent;
        const audioLevel =
          trackAudio && Number.isFinite(Number(trackAudio.audioLevel))
            ? Number(trackAudio.audioLevel).toFixed(4)
            : "n/a";
        log(
          `outbound audio: bytes_total=${bytesSent} packets_total=${packetsSent} bytes_delta=${deltaBytes} packets_delta=${deltaPackets} audio_level=${audioLevel}`
        );
      } catch (_error) {
        // keep stats timer best-effort
      }
    }, 2000);
  }

  async function stopOutboundAudioPipeline() {
    stopOutboundStats();
    if (state.outboundWebRtcStream) {
      stopTracks(state.outboundWebRtcStream);
      state.outboundWebRtcStream = null;
    }
    if (state.outboundAudioSource) {
      try {
        state.outboundAudioSource.disconnect();
      } catch (_error) {
        // no-op
      }
      state.outboundAudioSource = null;
    }
    if (state.outboundAudioGain) {
      try {
        state.outboundAudioGain.disconnect();
      } catch (_error) {
        // no-op
      }
      state.outboundAudioGain = null;
    }
    if (state.outboundAudioDestination) {
      try {
        state.outboundAudioDestination.disconnect();
      } catch (_error) {
        // no-op
      }
      state.outboundAudioDestination = null;
    }
    if (state.outboundAudioContext) {
      try {
        await state.outboundAudioContext.close();
      } catch (_error) {
        // no-op
      }
      state.outboundAudioContext = null;
    }
  }

  async function stopDirectIngestPipeline() {
    if (state.directPcmProcessor) {
      try {
        state.directPcmProcessor.disconnect();
      } catch (_error) {
        // no-op
      }
      state.directPcmProcessor.onaudioprocess = null;
      state.directPcmProcessor = null;
    }
    if (state.directPcmSource) {
      try {
        state.directPcmSource.disconnect();
      } catch (_error) {
        // no-op
      }
      state.directPcmSource = null;
    }
    if (state.directPcmSink) {
      try {
        state.directPcmSink.disconnect();
      } catch (_error) {
        // no-op
      }
      state.directPcmSink = null;
    }
    if (state.directPcmContext) {
      try {
        await state.directPcmContext.close();
      } catch (_error) {
        // no-op
      }
      state.directPcmContext = null;
    }
    if (state.directIngestWs) {
      try {
        state.directIngestWs.close();
      } catch (_error) {
        // no-op
      }
      state.directIngestWs = null;
    }
    logDirectPcmStatsIfNeeded(true);
  }

  async function startDirectIngestPipeline(workerUrl, sessionId, pairCode, stream) {
    await stopDirectIngestPipeline();
    if (!workerUrl || !sessionId || !pairCode || !stream) {
      return;
    }

    const ingestWsUrl = wsUrlFromHttp(
      workerUrl,
      `/ws/remote/audio_ingest?session_id=${encodeURIComponent(sessionId)}&pair_code=${encodeURIComponent(pairCode)}`
    );
    const directIngestWs = new WebSocket(ingestWsUrl);
    directIngestWs.binaryType = "arraybuffer";
    state.directIngestWs = directIngestWs;
    resetDirectPcmStats();

    directIngestWs.onopen = () => {
      log("direct ingest websocket connected");
    };
    directIngestWs.onerror = () => {
      log("direct ingest websocket error");
    };
    directIngestWs.onmessage = (event) => {
      let payload = null;
      try {
        payload = JSON.parse(String(event.data || ""));
      } catch (_error) {
        return;
      }
      if (!payload || typeof payload !== "object") return;
      if (String(payload.type || "").toLowerCase() === "error") {
        log(`direct ingest error: ${payload.message || "unknown"}`);
      }
    };
    directIngestWs.onclose = () => {
      if (!state.manualStop && !state.isClosing) {
        log("direct ingest websocket closed");
      }
    };

    const context = new window.AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const sink = context.createGain();
    sink.gain.value = 0;

    processor.onaudioprocess = (event) => {
      const channelData = event.inputBuffer.getChannelData(0);
      const rms = frameRms(channelData);
      if (!state.directIngestWs || state.directIngestWs.readyState !== WebSocket.OPEN) {
        state.directPcmChunksDropped += 1;
        state.directPcmRmsAccumulator += rms;
        state.directPcmRmsSamples += 1;
        logDirectPcmStatsIfNeeded(false);
        return;
      }
      const pcm = downsampleFloatToInt16(channelData, event.inputBuffer.sampleRate, 16000);
      if (!pcm || pcm.byteLength <= 0) return;
      try {
        state.directIngestWs.send(pcm.buffer);
        state.directPcmChunksSent += 1;
        state.directPcmBytesSent += pcm.byteLength;
        state.directPcmRmsAccumulator += rms;
        state.directPcmRmsSamples += 1;
        logDirectPcmStatsIfNeeded(false);
      } catch (_error) {
        state.directPcmChunksDropped += 1;
        state.directPcmRmsAccumulator += rms;
        state.directPcmRmsSamples += 1;
        logDirectPcmStatsIfNeeded(false);
      }
    };

    source.connect(processor);
    processor.connect(sink);
    sink.connect(context.destination);
    state.directPcmContext = context;
    state.directPcmSource = source;
    state.directPcmProcessor = processor;
    state.directPcmSink = sink;
    log(`direct ingest pipeline active; audio context state=${context.state}`);
  }

  async function createOutboundWebRtcStream(stream) {
    await stopOutboundAudioPipeline();
    if (!stream) return null;
    const context = new window.AudioContext();
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const gain = context.createGain();
    gain.gain.value = 1.0;
    const destination = context.createMediaStreamDestination();
    source.connect(gain);
    gain.connect(destination);
    const outboundStream = destination.stream;
    state.outboundAudioContext = context;
    state.outboundAudioSource = source;
    state.outboundAudioGain = gain;
    state.outboundAudioDestination = destination;
    state.outboundWebRtcStream = outboundStream;
    const outboundTrack = outboundStream.getAudioTracks()[0] || null;
    if (outboundTrack) {
      log(
        `outbound track state: enabled=${Boolean(outboundTrack.enabled)} muted=${Boolean(
          outboundTrack.muted
        )} readyState=${String(outboundTrack.readyState || "unknown")}`
      );
    } else {
      log("outbound track is missing on normalized WebRTC stream");
    }
    return outboundStream;
  }

  function describeIceCandidate(candidate) {
    if (!candidate || typeof candidate.candidate !== "string") {
      return "candidate=none";
    }
    const raw = String(candidate.candidate || "").trim();
    if (!raw) {
      return "candidate=end";
    }
    const parts = raw.split(/\s+/);
    const protocol = parts.length >= 3 ? String(parts[2] || "") : "";
    const typeIndex = parts.findIndex((value) => value === "typ");
    const candidateType = typeIndex >= 0 && parts.length > typeIndex + 1 ? String(parts[typeIndex + 1] || "") : "";
    return `candidate=${candidateType || "unknown"} proto=${protocol || "unknown"}`;
  }

  function parseFmtpValueMap(body) {
    const map = new Map();
    if (!body) return map;
    String(body)
      .split(";")
      .map((part) => String(part || "").trim())
      .filter(Boolean)
      .forEach((item) => {
        const eqIndex = item.indexOf("=");
        if (eqIndex <= 0) {
          map.set(item.toLowerCase(), "");
          return;
        }
        const key = item.slice(0, eqIndex).trim().toLowerCase();
        const value = item.slice(eqIndex + 1).trim();
        map.set(key, value);
      });
    return map;
  }

  function fmtpValueMapToString(map) {
    const parts = [];
    map.forEach((value, key) => {
      if (!key) return;
      parts.push(value === "" ? key : `${key}=${value}`);
    });
    return parts.join(";");
  }

  function tuneOpusOfferSdp(sdpText) {
    const sdp = String(sdpText || "");
    if (!sdp) return sdp;
    const lines = sdp.split("\r\n");
    let opusPayloadType = "";
    let rtpmapIndex = -1;
    for (let i = 0; i < lines.length; i += 1) {
      const line = String(lines[i] || "");
      const match = line.match(/^a=rtpmap:(\d+)\s+opus\/48000/i);
      if (match) {
        opusPayloadType = String(match[1] || "");
        rtpmapIndex = i;
        break;
      }
    }
    if (!opusPayloadType) {
      return sdp;
    }

    const fmtpPrefix = `a=fmtp:${opusPayloadType} `;
    let fmtpIndex = -1;
    for (let i = 0; i < lines.length; i += 1) {
      if (String(lines[i] || "").startsWith(fmtpPrefix)) {
        fmtpIndex = i;
        break;
      }
    }

    const fmtpMap = parseFmtpValueMap(
      fmtpIndex >= 0 ? String(lines[fmtpIndex] || "").slice(fmtpPrefix.length) : ""
    );
    if (WEBRTC_AUDIO_DISABLE_DTX) {
      fmtpMap.set("usedtx", "0");
    }
    if (WEBRTC_AUDIO_ENABLE_FEC) {
      fmtpMap.set("useinbandfec", "1");
    }
    if (WEBRTC_AUDIO_FORCE_CBR) {
      fmtpMap.set("cbr", "1");
    }
    if (Number.isFinite(WEBRTC_AUDIO_MAX_BITRATE_BPS) && WEBRTC_AUDIO_MAX_BITRATE_BPS > 0) {
      fmtpMap.set("maxaveragebitrate", String(Math.floor(WEBRTC_AUDIO_MAX_BITRATE_BPS)));
    }

    const tunedFmtp = `${fmtpPrefix}${fmtpValueMapToString(fmtpMap)}`;
    if (fmtpIndex >= 0) {
      lines[fmtpIndex] = tunedFmtp;
    } else if (rtpmapIndex >= 0) {
      lines.splice(rtpmapIndex + 1, 0, tunedFmtp);
    }

    const ptimeLine = `a=ptime:${Math.max(10, Math.floor(WEBRTC_AUDIO_PTIME_MS))}`;
    const ptimeIndex = lines.findIndex((line) => String(line || "").startsWith("a=ptime:"));
    if (ptimeIndex >= 0) {
      lines[ptimeIndex] = ptimeLine;
    } else {
      lines.push(ptimeLine);
    }

    return lines.join("\r\n");
  }

  async function tuneAudioSenderForSpeech(sender) {
    if (!sender || typeof sender.getParameters !== "function" || typeof sender.setParameters !== "function") {
      return;
    }
    try {
      const parameters = sender.getParameters() || {};
      if (!Array.isArray(parameters.encodings) || parameters.encodings.length <= 0) {
        parameters.encodings = [{}];
      }
      const encoding = parameters.encodings[0] || {};
      if (Number.isFinite(WEBRTC_AUDIO_MAX_BITRATE_BPS) && WEBRTC_AUDIO_MAX_BITRATE_BPS > 0) {
        encoding.maxBitrate = Math.floor(WEBRTC_AUDIO_MAX_BITRATE_BPS);
      }
      if (WEBRTC_AUDIO_DISABLE_DTX) {
        encoding.dtx = "disabled";
      }
      parameters.encodings[0] = encoding;
      await sender.setParameters(parameters);
      log(
        `audio sender tuned: maxBitrate=${String(encoding.maxBitrate || "n/a")} dtx=${String(
          encoding.dtx || "default"
        )}`
      );
    } catch (error) {
      log(`audio sender tuning skipped: ${error}`);
    }
  }

  function isFatalPairingMessage(message) {
    const text = String(message || "").trim().toLowerCase();
    if (!text) return false;
    return (
      text.includes("pairing session has expired") ||
      text.includes("pairing rejected") ||
      text.includes("session id does not match") ||
      text.includes("pair code does not match")
    );
  }

  async function handleSignalPayload(payload) {
    if (!state.pc || !payload || typeof payload !== "object") return;
    const type = String(payload.type || "").toLowerCase();
    if (type === "answer" && payload.sdp) {
      await state.pc.setRemoteDescription(payload.sdp);
      log("remote answer applied");
      return;
    }
    if (type === "ice" && payload.candidate) {
      try {
        await state.pc.addIceCandidate(payload.candidate);
        log(`remote ${describeIceCandidate(payload.candidate)}`);
      } catch (error) {
        log(`ice add failed: ${error}`);
      }
    }
  }

  async function closeSocket(socket) {
    if (!socket) return;
    try {
      socket.close();
    } catch (_error) {
      // no-op
    }
  }

  async function stopBridge(options = {}) {
    const manual = options.manual !== false;
    const silent = options.silent === true;
    if (manual) {
      state.manualStop = true;
      resetReconnectState();
    }
    state.running = false;
    state.isClosing = true;

    if (state.heartbeatTimer) {
      window.clearInterval(state.heartbeatTimer);
      state.heartbeatTimer = null;
    }

    await closeSocket(state.signalingWs);
    await closeSocket(state.remoteEventsWs);
    await closeSocket(state.localIngestWs);
    state.signalingWs = null;
    state.remoteEventsWs = null;
    state.localIngestWs = null;

    if (state.pc) {
      try {
        state.pc.close();
      } catch (_error) {
        // no-op
      }
      state.pc = null;
    }
    if (state.localStream) {
      stopTracks(state.localStream);
      state.localStream = null;
    }
    await stopDirectIngestPipeline();
    await stopOutboundAudioPipeline();
    await stopMicMonitor();
    logMicRmsIfNeeded(true);

    if (!silent) {
      setStatus(manual ? "Stopped." : "Bridge restarted.", "warn");
      if (manual) {
        log("bridge stopped");
      }
    }
  }

  async function startEventForwarding(workerUrl) {
    const localIngestUrl = `${currentWsOrigin()}/ws/remote/result_ingest`;
    const remoteEventsUrl = wsUrlFromHttp(workerUrl, "/ws/events");

    const localIngestWs = new WebSocket(localIngestUrl);
    state.localIngestWs = localIngestWs;
    localIngestWs.onopen = () => {
      log("local result ingest connected");
    };
    localIngestWs.onerror = () => {
      log("local result ingest websocket error");
    };
    localIngestWs.onclose = () => {
      if (state.running && !state.manualStop && !state.isClosing) {
        log("local result ingest websocket closed");
        scheduleReconnect("local result ingest websocket closed");
      }
    };

    const remoteEventsWs = new WebSocket(remoteEventsUrl);
    state.remoteEventsWs = remoteEventsWs;
    remoteEventsWs.onopen = () => {
      log("remote worker events websocket connected");
    };
    remoteEventsWs.onerror = () => {
      log("remote worker events websocket error");
    };
    remoteEventsWs.onclose = () => {
      if (state.running && !state.manualStop && !state.isClosing) {
        log("remote worker events websocket closed");
        scheduleReconnect("remote worker events websocket closed");
      }
    };
    remoteEventsWs.onmessage = (event) => {
      let payload = null;
      try {
        payload = JSON.parse(String(event.data || ""));
      } catch (_error) {
        return;
      }
      if (!payload || typeof payload !== "object") return;
      const type = String(payload.type || "").toLowerCase();
      if (type !== "transcript_update" && type !== "translation_update") {
        return;
      }
      if (!state.localIngestWs || state.localIngestWs.readyState !== WebSocket.OPEN) {
        return;
      }
      try {
        state.localIngestWs.send(
          JSON.stringify({
            type,
            payload: payload.payload || {},
          })
        );
      } catch (_error) {
        // ignore one-off send failures
      }
    };
  }

  async function startBridge() {
    await stopBridge({ manual: false, silent: true });
    state.manualStop = false;
    state.isClosing = false;
    state.fatalPairingError = false;

    const workerUrl = normalizeBaseUrl(workerUrlInput?.value || "");
    const sessionId = String(sessionIdInput?.value || "").trim();
    const pairCode = String(pairCodeInput?.value || "").trim();
    if (!workerUrl || !sessionId || !pairCode) {
      state.manualStop = true;
      setStatus("Worker URL, Session ID, and Pair Code are required.", "bad");
      return;
    }
    persistValues();

    if (!state.micPermissionPrimed) {
      await refreshMicrophones(true);
    }

    const selectedMicId = currentMicSelection();
    const captureAudioConstraints = {
      channelCount: 1,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    };

    setStatus("Requesting microphone access...", "warn");
    try {
      state.localStream = await navigator.mediaDevices.getUserMedia({
        audio: selectedMicId
          ? {
              ...captureAudioConstraints,
              deviceId: { exact: selectedMicId },
            }
          : captureAudioConstraints,
        video: false,
      });
    } catch (error) {
      if (!selectedMicId) {
        throw error;
      }
      log(`selected microphone failed, fallback to default: ${error}`);
      state.localStream = await navigator.mediaDevices.getUserMedia({
        audio: captureAudioConstraints,
        video: false,
      });
      if (micSelect) {
        micSelect.value = "";
      }
    }
    persistValues();
    const selectedMicLabel =
      micSelect && micSelect.selectedIndex >= 0
        ? String(micSelect.options[micSelect.selectedIndex]?.textContent || "").trim()
        : "";
    log(`microphone capture active: ${selectedMicLabel || "default microphone"}`);
    await startMicMonitor(state.localStream);
    if (DIRECT_PCM_FALLBACK_ENABLED) {
      await startDirectIngestPipeline(workerUrl, sessionId, pairCode, state.localStream);
      log("direct PCM fallback: enabled");
    } else {
      await stopDirectIngestPipeline();
      log("direct PCM fallback: disabled");
    }
    let outboundStream = null;
    if (WEBRTC_USE_RAW_MIC_TRACK) {
      log("webRTC source mode: raw microphone track");
    } else {
      outboundStream = await createOutboundWebRtcStream(state.localStream);
      log("webRTC source mode: normalized media stream destination");
    }

    state.pc = new RTCPeerConnection({
      iceServers: ICE_SERVERS,
      iceTransportPolicy: "all",
    });
    const streamForPeer = outboundStream || state.localStream;
    streamForPeer.getTracks().forEach((track) => {
      track.enabled = true;
      const sender = state.pc.addTrack(track, streamForPeer);
      log(`sender track added: kind=${track.kind} enabled=${Boolean(track.enabled)} readyState=${track.readyState}`);
      if (track.kind === "audio" && WEBRTC_AUDIO_SENDER_TUNING_ENABLED) {
        tuneAudioSenderForSpeech(sender);
      }
    });
    state.pc.onicecandidate = (event) => {
      log(`local ${describeIceCandidate(event.candidate)}`);
      if (!event.candidate) return;
      sendSignal({ type: "ice", candidate: event.candidate });
    };
    state.pc.oniceconnectionstatechange = () => {
      log(`ice state: ${state.pc?.iceConnectionState || "unknown"}`);
    };
    state.pc.onconnectionstatechange = () => {
      log(`pc state: ${state.pc?.connectionState || "unknown"}`);
      if (state.pc?.connectionState === "connected") {
        setStatus("WebRTC stream is connected to remote worker.", "ok");
      }
      if (state.pc?.connectionState === "failed") {
        setStatus("WebRTC connection failed.", "bad");
        scheduleReconnect("webrtc connection failed");
      }
      if (state.pc?.connectionState === "disconnected" && !state.manualStop) {
        scheduleReconnect("webrtc connection disconnected");
      }
    };

    const signalWsUrl = wsUrlFromHttp(
      workerUrl,
      `/ws/remote/signaling?session_id=${encodeURIComponent(sessionId)}&pair_code=${encodeURIComponent(
        pairCode
      )}&role=controller`
    );
    const signalingWs = new WebSocket(signalWsUrl);
    state.signalingWs = signalingWs;
    setStatus("Connecting to remote signaling...", "warn");
    log(`signaling -> ${signalWsUrl}`);
    log(`signaling websocket state=${signalingWs.readyState}`);

    signalingWs.onopen = async () => {
      state.running = true;
      resetReconnectState();
      setStatus("Signaling connected. Creating offer...", "warn");
      await startEventForwarding(workerUrl);
      state.heartbeatTimer = window.setInterval(() => {
        if (state.signalingWs?.readyState === WebSocket.OPEN) {
          state.signalingWs.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 5000);
      const offer = await state.pc.createOffer({
        offerToReceiveAudio: true,
        offerToReceiveVideo: false,
      });
      const tunedOffer = WEBRTC_AUDIO_SDP_TUNING_ENABLED
        ? {
            type: offer.type,
            sdp: tuneOpusOfferSdp(offer.sdp),
          }
        : offer;
      await state.pc.setLocalDescription(tunedOffer);
      if (WEBRTC_AUDIO_SDP_TUNING_ENABLED) {
        log(
          `offer tuned: opus_max_bitrate=${WEBRTC_AUDIO_MAX_BITRATE_BPS} fec=${WEBRTC_AUDIO_ENABLE_FEC} dtx_disabled=${WEBRTC_AUDIO_DISABLE_DTX} ptime=${WEBRTC_AUDIO_PTIME_MS}`
        );
      }
      sendSignal({ type: "offer", sdp: state.pc.localDescription });
      log("offer sent");
      startOutboundStats();
    };

    signalingWs.onmessage = async (event) => {
      let message = null;
      try {
        message = JSON.parse(String(event.data || ""));
      } catch (_error) {
        return;
      }
      if (!message || typeof message !== "object") return;
      const messageType = String(message.type || "").toLowerCase();
      if (messageType === "signal") {
        await handleSignalPayload(message.payload || {});
        return;
      }
      if (messageType === "warning") {
        log(`warning: ${message.message || "unknown warning"}`);
        setStatus("Waiting for worker bridge peer...", "warn");
        return;
      }
      if (messageType === "peer_state") {
        const workerConnected = Boolean(message.worker_connected);
        setStatus(workerConnected ? "Worker bridge connected." : "Waiting for worker bridge peer...", workerConnected ? "ok" : "warn");
        return;
      }
      if (messageType === "error") {
        const errorMessage = String(message.message || "unknown");
        setStatus(`Signaling error: ${errorMessage}`, "bad");
        log(`error: ${errorMessage}`);
        if (isFatalPairingMessage(errorMessage)) {
          state.fatalPairingError = true;
          state.manualStop = true;
          resetReconnectState();
          setStatus("Pairing expired or invalid. Create a new pair and start bridge again.", "bad");
          log("fatal pairing error detected; automatic reconnect is stopped");
        }
      }
    };

    signalingWs.onerror = () => {
      log(`signaling websocket error (state=${signalingWs.readyState})`);
    };

    signalingWs.onclose = (event) => {
      log(`signaling websocket closed: code=${Number(event?.code || 0)} reason=${String(event?.reason || "")}`);
      if (state.running) {
        setStatus("Signaling disconnected.", "warn");
      }
      state.running = false;
      if (!state.manualStop && !state.isClosing) {
        scheduleReconnect("signaling websocket closed");
      }
    };
  }

  const preset = parseQuery();
  loadPersistedValues();
  if (workerUrlInput && preset.workerUrl) {
    workerUrlInput.value = preset.workerUrl;
  }
  if (sessionIdInput && preset.sessionId) {
    sessionIdInput.value = preset.sessionId;
  }
  if (pairCodeInput && preset.pairCode) {
    pairCodeInput.value = preset.pairCode;
  }
  if (micSelect && preset.micId) {
    try {
      localStorage.setItem(STORE_KEYS.micId, preset.micId);
    } catch (_error) {
      // ignore localStorage failures
    }
  }

  [workerUrlInput, sessionIdInput, pairCodeInput].forEach((element) => {
    element?.addEventListener("input", persistValues);
  });
  micSelect?.addEventListener("change", persistValues);

  connectBtn?.addEventListener("click", () => {
    startBridge().catch((error) => {
      setStatus(`Start failed: ${error}`, "bad");
      log(`start failed: ${error}`);
    });
  });

  stopBtn?.addEventListener("click", () => {
    stopBridge({ manual: true }).catch((error) => {
      setStatus(`Stop failed: ${error}`, "bad");
    });
  });

  refreshMicsBtn?.addEventListener("click", () => {
    refreshMicrophones(true).catch((error) => {
      setStatus(`Microphone refresh failed: ${error}`, "bad");
      log(`microphone refresh failed: ${error}`);
    });
  });

  if (navigator.mediaDevices && typeof navigator.mediaDevices.addEventListener === "function") {
    navigator.mediaDevices.addEventListener("devicechange", () => {
      refreshMicrophones(false).catch(() => {
        // device refresh is best effort
      });
    });
  }

  window.addEventListener("beforeunload", () => {
    stopBridge({ manual: true, silent: true }).catch(() => {
      // best effort on window close
    });
  });

  refreshMicrophones(false).catch((error) => {
    log(`initial microphone refresh failed: ${error}`);
  });
})();
