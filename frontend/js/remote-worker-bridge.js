(function () {
  const sessionIdInput = document.getElementById("session-id");
  const pairCodeInput = document.getElementById("pair-code");
  const connectBtn = document.getElementById("connect-btn");
  const stopBtn = document.getElementById("stop-btn");
  const statusLine = document.getElementById("status-line");
  const logBox = document.getElementById("log-box");
  const monitorAudio = document.getElementById("monitor-audio");

  const STORE_KEYS = {
    sessionId: "sst.remote.worker_bridge.session_id",
    pairCode: "sst.remote.worker_bridge.pair_code",
  };
  const RECONNECT_BASE_MS = 1000;
  const RECONNECT_MAX_MS = 30000;
  const ICE_SERVERS = [
    { urls: "stun:stun.cloudflare.com:3478" },
    { urls: "stun:stun.l.google.com:19302" },
  ];
  const WORKLET_MODULE_URL = "/static/js/remote-worker-audio-worklet.js?v=20260422a";
  const WORKLET_CHUNK_SAMPLES = 2048;
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
    ingestWs: null,
    pc: null,
    heartbeatTimer: null,
    running: false,
    audioContext: null,
    sourceNode: null,
    processorNode: null,
    workletNode: null,
    sinkNode: null,
    audioPipelineMode: null,
    manualStop: true,
    isClosing: false,
    reconnectTimer: null,
    reconnectAttempt: 0,
    fatalPairingError: false,
    pcmWindowStartedAt: 0,
    pcmChunksSent: 0,
    pcmBytesSent: 0,
    pcmRmsAccumulator: 0,
    pcmRmsSamples: 0,
    pcmChunksDropped: 0,
    pcmFirstChunkLogged: false,
    channelRmsSamples: 0,
    channel0RmsAccumulator: 0,
    channel1RmsAccumulator: 0,
    channelMaxRmsAccumulator: 0,
    receiverStatsTimer: null,
    receiverStatsSnapshot: null,
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
      text.startsWith("pcm tx:") ||
      text.startsWith("inbound audio:") ||
      text.startsWith("inbound audio stats:") ||
      text.startsWith("local candidate=") ||
      text.startsWith("remote candidate=")
    );
  }

  function setStatus(message, level) {
    if (!statusLine) return;
    statusLine.classList.remove("ok", "warn", "bad");
    if (level) statusLine.classList.add(level);
    statusLine.textContent = message;
  }

  function parseQuery() {
    const params = new URLSearchParams(window.location.search);
    return {
      sessionId: String(params.get("session_id") || "").trim(),
      pairCode: String(params.get("pair_code") || "").trim(),
    };
  }

  function loadPersistedValues() {
    try {
      sessionIdInput.value = localStorage.getItem(STORE_KEYS.sessionId) || sessionIdInput.value || "";
      pairCodeInput.value = localStorage.getItem(STORE_KEYS.pairCode) || pairCodeInput.value || "";
    } catch (_error) {
      // ignore localStorage failures
    }
  }

  function persistValues() {
    try {
      localStorage.setItem(STORE_KEYS.sessionId, String(sessionIdInput?.value || "").trim());
      localStorage.setItem(STORE_KEYS.pairCode, String(pairCodeInput?.value || "").trim());
    } catch (_error) {
      // ignore localStorage failures
    }
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

  function extractMonoFromInputBuffer(inputBuffer) {
    if (!inputBuffer || typeof inputBuffer.getChannelData !== "function") {
      return new Float32Array(0);
    }
    const channelCount = Math.max(1, Number(inputBuffer.numberOfChannels) || 1);
    const frameLength = Number(inputBuffer.length) || 0;
    if (frameLength <= 0) {
      return new Float32Array(0);
    }
    if (channelCount === 1) {
      return new Float32Array(inputBuffer.getChannelData(0));
    }
    const mixed = new Float32Array(frameLength);
    for (let channel = 0; channel < channelCount; channel += 1) {
      const source = inputBuffer.getChannelData(channel);
      for (let i = 0; i < frameLength; i += 1) {
        mixed[i] += source[i];
      }
    }
    const scale = 1 / channelCount;
    for (let i = 0; i < frameLength; i += 1) {
      mixed[i] *= scale;
    }
    return mixed;
  }

  function collectChannelRms(inputBuffer) {
    if (!inputBuffer || typeof inputBuffer.getChannelData !== "function") {
      return { ch0: 0, ch1: 0, max: 0 };
    }
    const channelCount = Math.max(1, Number(inputBuffer.numberOfChannels) || 1);
    const ch0 = frameRms(inputBuffer.getChannelData(0));
    const ch1 = channelCount > 1 ? frameRms(inputBuffer.getChannelData(1)) : 0;
    return {
      ch0,
      ch1,
      max: Math.max(ch0, ch1),
    };
  }

  function resetPcmStats() {
    state.pcmWindowStartedAt = performance.now();
    state.pcmChunksSent = 0;
    state.pcmBytesSent = 0;
    state.pcmRmsAccumulator = 0;
    state.pcmRmsSamples = 0;
    state.pcmChunksDropped = 0;
    state.pcmFirstChunkLogged = false;
    state.channelRmsSamples = 0;
    state.channel0RmsAccumulator = 0;
    state.channel1RmsAccumulator = 0;
    state.channelMaxRmsAccumulator = 0;
  }

  function logPcmStatsIfNeeded(force) {
    const now = performance.now();
    if (!force && now - state.pcmWindowStartedAt < 2000) {
      return;
    }
    const seconds = Math.max(0.001, (now - state.pcmWindowStartedAt) / 1000);
    const kbps = (state.pcmBytesSent * 8) / 1000 / seconds;
    const avgRms = state.pcmRmsSamples > 0 ? state.pcmRmsAccumulator / state.pcmRmsSamples : 0;
    const avgCh0 = state.channelRmsSamples > 0 ? state.channel0RmsAccumulator / state.channelRmsSamples : 0;
    const avgCh1 = state.channelRmsSamples > 0 ? state.channel1RmsAccumulator / state.channelRmsSamples : 0;
    const avgChMax = state.channelRmsSamples > 0 ? state.channelMaxRmsAccumulator / state.channelRmsSamples : 0;
    const wsState = state.ingestWs ? state.ingestWs.readyState : WebSocket.CLOSED;
    log(
      `pcm tx: chunks=${state.pcmChunksSent} dropped=${state.pcmChunksDropped} bytes=${state.pcmBytesSent} avg_rms=${avgRms.toFixed(
        4
      )} ch0=${avgCh0.toFixed(4)} ch1=${avgCh1.toFixed(4)} ch_max=${avgChMax.toFixed(4)} rate_kbps=${kbps.toFixed(
        1
      )} ingest_ws_state=${wsState}`
    );
    state.pcmWindowStartedAt = now;
    state.pcmChunksSent = 0;
    state.pcmBytesSent = 0;
    state.pcmRmsAccumulator = 0;
    state.pcmRmsSamples = 0;
    state.pcmChunksDropped = 0;
    state.channelRmsSamples = 0;
    state.channel0RmsAccumulator = 0;
    state.channel1RmsAccumulator = 0;
    state.channelMaxRmsAccumulator = 0;
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

  function stopReceiverStats() {
    if (state.receiverStatsTimer) {
      window.clearInterval(state.receiverStatsTimer);
      state.receiverStatsTimer = null;
    }
    state.receiverStatsSnapshot = null;
  }

  function startReceiverStats() {
    stopReceiverStats();
    state.receiverStatsTimer = window.setInterval(async () => {
      if (!state.pc || state.pc.connectionState !== "connected") {
        state.receiverStatsSnapshot = null;
        return;
      }
      try {
        const report = await state.pc.getStats();
        let inboundAudio = null;
        report.forEach((entry) => {
          if (inboundAudio) return;
          if (!entry || entry.type !== "inbound-rtp" || entry.kind !== "audio") return;
          inboundAudio = entry;
        });
        if (!inboundAudio) {
          log("inbound audio stats: unavailable");
          return;
        }
        const snapshot = {
          bytesReceived: Number(inboundAudio.bytesReceived || 0),
          packetsReceived: Number(inboundAudio.packetsReceived || 0),
          totalAudioEnergy: Number(inboundAudio.totalAudioEnergy || 0),
          totalSamplesDuration: Number(inboundAudio.totalSamplesDuration || 0),
          jitterBufferEmittedCount: Number(inboundAudio.jitterBufferEmittedCount || 0),
          concealedSamples: Number(inboundAudio.concealedSamples || 0),
          silentConcealedSamples: Number(inboundAudio.silentConcealedSamples || 0),
          audioLevel:
            inboundAudio.audioLevel == null || Number.isNaN(Number(inboundAudio.audioLevel))
              ? null
              : Number(inboundAudio.audioLevel),
        };
        const prev = state.receiverStatsSnapshot;
        if (prev) {
          const deltaBytes = snapshot.bytesReceived - prev.bytesReceived;
          const deltaPackets = snapshot.packetsReceived - prev.packetsReceived;
          const deltaEnergy = snapshot.totalAudioEnergy - prev.totalAudioEnergy;
          const deltaDuration = snapshot.totalSamplesDuration - prev.totalSamplesDuration;
          const deltaJitter = snapshot.jitterBufferEmittedCount - prev.jitterBufferEmittedCount;
          const deltaConcealed = snapshot.concealedSamples - prev.concealedSamples;
          const deltaSilentConcealed = snapshot.silentConcealedSamples - prev.silentConcealedSamples;
          const levelText = snapshot.audioLevel == null ? "n/a" : snapshot.audioLevel.toFixed(4);
          log(
            `inbound audio: bytes_delta=${Math.max(0, deltaBytes)} packets_delta=${Math.max(
              0,
              deltaPackets
            )} energy_delta=${Math.max(0, deltaEnergy).toFixed(6)} duration_delta=${Math.max(
              0,
              deltaDuration
            ).toFixed(3)} jitter_emitted_delta=${Math.max(0, deltaJitter)} concealed_delta=${Math.max(
              0,
              deltaConcealed
            )} silent_concealed_delta=${Math.max(0, deltaSilentConcealed)} audio_level=${levelText}`
          );
        }
        state.receiverStatsSnapshot = snapshot;
      } catch (error) {
        log(`inbound stats error: ${error}`);
      }
    }, 2000);
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

  function ingestMonoFrame(monoData, inputSampleRate, channelRms) {
    const frame = monoData instanceof Float32Array ? monoData : new Float32Array(monoData || []);
    if (!frame || frame.length <= 0) return;

    const ch0 = Number(channelRms?.ch0 || 0);
    const ch1 = Number(channelRms?.ch1 || 0);
    const chMax = Number(channelRms?.max || Math.max(ch0, ch1));
    state.channelRmsSamples += 1;
    state.channel0RmsAccumulator += ch0;
    state.channel1RmsAccumulator += ch1;
    state.channelMaxRmsAccumulator += chMax;

    const rmsCandidate = Number(channelRms?.mono);
    const rms = Number.isFinite(rmsCandidate) ? rmsCandidate : frameRms(frame);
    if (!state.ingestWs || state.ingestWs.readyState !== WebSocket.OPEN) {
      state.pcmChunksDropped += 1;
      state.pcmRmsAccumulator += rms;
      state.pcmRmsSamples += 1;
      logPcmStatsIfNeeded(false);
      return;
    }
    const pcm = downsampleFloatToInt16(frame, inputSampleRate, 16000);
    if (!pcm || pcm.byteLength <= 0) return;
    try {
      state.ingestWs.send(pcm.buffer);
      state.pcmChunksSent += 1;
      state.pcmBytesSent += pcm.byteLength;
      state.pcmRmsAccumulator += rms;
      state.pcmRmsSamples += 1;
      if (!state.pcmFirstChunkLogged) {
        state.pcmFirstChunkLogged = true;
        log(`first pcm frame sent: bytes=${pcm.byteLength} rms=${rms.toFixed(4)}`);
      }
      logPcmStatsIfNeeded(false);
    } catch (_error) {
      // keep stream alive; transient websocket back-pressure can happen
      state.pcmChunksDropped += 1;
      state.pcmRmsAccumulator += rms;
      state.pcmRmsSamples += 1;
      logPcmStatsIfNeeded(false);
    }
  }

  async function stopAudioPipeline() {
    if (state.workletNode) {
      try {
        state.workletNode.disconnect();
      } catch (_error) {
        // no-op
      }
      try {
        state.workletNode.port.onmessage = null;
      } catch (_error) {
        // no-op
      }
      state.workletNode = null;
    }
    if (state.processorNode) {
      try {
        state.processorNode.disconnect();
      } catch (_error) {
        // no-op
      }
      state.processorNode.onaudioprocess = null;
      state.processorNode = null;
    }
    if (state.sourceNode) {
      try {
        state.sourceNode.disconnect();
      } catch (_error) {
        // no-op
      }
      state.sourceNode = null;
    }
    if (state.sinkNode) {
      try {
        state.sinkNode.disconnect();
      } catch (_error) {
        // no-op
      }
      state.sinkNode = null;
    }
    if (state.audioContext) {
      try {
        await state.audioContext.close();
      } catch (_error) {
        // no-op
      }
      state.audioContext = null;
    }
    if (monitorAudio) {
      try {
        monitorAudio.pause();
      } catch (_error) {
        // no-op
      }
      monitorAudio.srcObject = null;
    }
    state.audioPipelineMode = null;
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
    await closeSocket(state.ingestWs);
    state.signalingWs = null;
    state.ingestWs = null;
    stopReceiverStats();

    if (state.pc) {
      try {
        state.pc.close();
      } catch (_error) {
        // no-op
      }
      state.pc = null;
    }
    await stopAudioPipeline();
    logPcmStatsIfNeeded(true);

    if (!silent) {
      setStatus(manual ? "Stopped." : "Bridge restarted.", "warn");
      if (manual) {
        log("bridge stopped");
      }
    }
  }

  async function attachRemoteTrack(stream) {
    if (!stream) return;
    await stopAudioPipeline();
    if (monitorAudio) {
      monitorAudio.srcObject = stream;
      monitorAudio.muted = false;
      try {
        await monitorAudio.play();
        log("monitor audio playback started");
      } catch (error) {
        log(`monitor audio playback blocked: ${error}`);
      }
    }

    const audioContext = new window.AudioContext();
    await audioContext.resume();
    log(`audio context state: ${audioContext.state}`);
    const firstTrack = stream.getAudioTracks()[0] || null;
    if (firstTrack) {
      const trackSettings =
        typeof firstTrack.getSettings === "function" ? firstTrack.getSettings() || {} : {};
      log(
        `remote track state: enabled=${Boolean(firstTrack.enabled)} muted=${Boolean(firstTrack.muted)} readyState=${String(
          firstTrack.readyState || "unknown"
        )}`
      );
      log(
        `remote track settings: sampleRate=${String(trackSettings.sampleRate || "n/a")} channelCount=${String(
          trackSettings.channelCount || "n/a"
        )}`
      );
      firstTrack.onmute = () => log("remote track event: mute");
      firstTrack.onunmute = () => log("remote track event: unmute");
      firstTrack.onended = () => log("remote track event: ended");
    }
    let source = null;
    if (firstTrack && typeof audioContext.createMediaStreamTrackSource === "function") {
      try {
        source = audioContext.createMediaStreamTrackSource(firstTrack);
        log("audio source node: MediaStreamTrackAudioSourceNode");
      } catch (error) {
        log(`track source create failed, fallback to stream source: ${error}`);
      }
    }
    if (!source) {
      source = audioContext.createMediaStreamSource(stream);
      log("audio source node: MediaStreamAudioSourceNode");
    }
    const sink = audioContext.createGain();
    sink.gain.value = 0;
    state.audioContext = audioContext;
    state.sourceNode = source;
    state.sinkNode = sink;

    let workletAttached = false;
    if (audioContext.audioWorklet && typeof window.AudioWorkletNode === "function") {
      try {
        await audioContext.audioWorklet.addModule(WORKLET_MODULE_URL);
        const workletNode = new window.AudioWorkletNode(audioContext, "sst-remote-worker-audio-processor", {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          channelCount: 1,
          channelCountMode: "explicit",
          processorOptions: { chunkSize: WORKLET_CHUNK_SAMPLES },
        });
        workletNode.port.onmessage = (event) => {
          const payload = event?.data || {};
          if (String(payload.type || "") !== "audio-frame") return;
          const monoFrame = payload.samples instanceof Float32Array ? payload.samples : new Float32Array(payload.samples || []);
          ingestMonoFrame(monoFrame, Number(payload.sampleRate) || audioContext.sampleRate, {
            ch0: Number(payload.ch0Rms || 0),
            ch1: Number(payload.ch1Rms || 0),
            max: Number(payload.chMaxRms || 0),
            mono: Number(payload.monoRms),
          });
        };
        source.connect(workletNode);
        workletNode.connect(sink);
        sink.connect(audioContext.destination);
        state.workletNode = workletNode;
        state.audioPipelineMode = "audioworklet";
        workletAttached = true;
        log(`audio pipeline mode: AudioWorkletNode (chunk=${WORKLET_CHUNK_SAMPLES})`);
      } catch (error) {
        log(`audio worklet init failed, fallback to ScriptProcessor: ${error}`);
      }
    } else {
      log("audio worklet unavailable in this browser context, fallback to ScriptProcessor");
    }

    if (!workletAttached) {
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        const channelRms = collectChannelRms(event.inputBuffer);
        const monoData = extractMonoFromInputBuffer(event.inputBuffer);
        const rms = frameRms(monoData);
        ingestMonoFrame(monoData, event.inputBuffer.sampleRate, {
          ch0: channelRms.ch0,
          ch1: channelRms.ch1,
          max: channelRms.max,
          mono: rms,
        });
      };
      source.connect(processor);
      processor.connect(sink);
      sink.connect(audioContext.destination);
      state.processorNode = processor;
      state.audioPipelineMode = "scriptprocessor";
      log("audio pipeline mode: ScriptProcessorNode (fallback)");
    }

    log("remote audio forwarding pipeline is active");
  }

  async function handleSignalPayload(payload) {
    if (!payload || typeof payload !== "object" || !state.pc) return;
    const type = String(payload.type || "").toLowerCase();
    if (type === "offer" && payload.sdp) {
      await state.pc.setRemoteDescription(payload.sdp);
      const answer = await state.pc.createAnswer();
      await state.pc.setLocalDescription(answer);
      sendSignal({ type: "answer", sdp: state.pc.localDescription });
      log("offer received, answer sent");
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

  async function startBridge() {
    await stopBridge({ manual: false, silent: true });
    state.manualStop = false;
    state.isClosing = false;
    state.fatalPairingError = false;
    resetPcmStats();

    const sessionId = String(sessionIdInput?.value || "").trim();
    const pairCode = String(pairCodeInput?.value || "").trim();
    if (!sessionId || !pairCode) {
      state.manualStop = true;
      setStatus("Session ID and Pair Code are required.", "bad");
      return;
    }
    persistValues();

    const wsOrigin = currentWsOrigin();
    const signalWsUrl = `${wsOrigin}/ws/remote/signaling?session_id=${encodeURIComponent(
      sessionId
    )}&pair_code=${encodeURIComponent(pairCode)}&role=worker`;
    const ingestWsUrl = `${wsOrigin}/ws/remote/audio_ingest?session_id=${encodeURIComponent(
      sessionId
    )}&pair_code=${encodeURIComponent(pairCode)}`;

    state.ingestWs = new WebSocket(ingestWsUrl);
    state.ingestWs.binaryType = "arraybuffer";
    state.ingestWs.onopen = () => {
      log("audio ingest websocket connected");
    };
    state.ingestWs.onerror = () => {
      log("audio ingest websocket error");
    };
    state.ingestWs.onclose = () => {
      if (state.running && !state.manualStop && !state.isClosing) {
        log("audio ingest websocket closed");
        scheduleReconnect("audio ingest websocket closed");
      }
    };

    state.pc = new RTCPeerConnection({
      iceServers: ICE_SERVERS,
      iceTransportPolicy: "all",
    });
    startReceiverStats();
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
        setStatus("WebRTC connection established. Forwarding audio to local worker.", "ok");
      }
      if (state.pc?.connectionState === "failed") {
        setStatus("WebRTC connection failed.", "bad");
        scheduleReconnect("webrtc connection failed");
      }
      if (state.pc?.connectionState === "disconnected" && !state.manualStop) {
        scheduleReconnect("webrtc connection disconnected");
      }
    };
    state.pc.ontrack = async (event) => {
      const stream = event.streams?.[0] || new MediaStream([event.track]);
      await attachRemoteTrack(stream);
    };

    state.signalingWs = new WebSocket(signalWsUrl);
    setStatus("Connecting worker signaling...", "warn");
    log(`signaling -> ${signalWsUrl}`);

    state.signalingWs.onopen = () => {
      state.running = true;
      resetReconnectState();
      setStatus("Worker signaling connected. Waiting for controller offer...", "warn");
      state.heartbeatTimer = window.setInterval(() => {
        if (state.signalingWs?.readyState === WebSocket.OPEN) {
          state.signalingWs.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 5000);
    };

    state.signalingWs.onmessage = async (event) => {
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
      if (messageType === "peer_state") {
        const controllerConnected = Boolean(message.controller_connected);
        setStatus(
          controllerConnected
            ? "Controller peer is connected."
            : "Waiting for controller peer...",
          controllerConnected ? "ok" : "warn"
        );
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

    state.signalingWs.onerror = () => {
      log("worker signaling websocket error");
    };
    state.signalingWs.onclose = () => {
      if (state.running) {
        setStatus("Worker signaling websocket disconnected.", "warn");
      }
      state.running = false;
      if (!state.manualStop && !state.isClosing) {
        scheduleReconnect("worker signaling websocket closed");
      }
    };
  }

  const preset = parseQuery();
  loadPersistedValues();
  if (sessionIdInput && preset.sessionId) {
    sessionIdInput.value = preset.sessionId;
  }
  if (pairCodeInput && preset.pairCode) {
    pairCodeInput.value = preset.pairCode;
  }

  [sessionIdInput, pairCodeInput].forEach((element) => {
    element?.addEventListener("input", persistValues);
  });

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

  window.addEventListener("beforeunload", () => {
    stopBridge({ manual: true, silent: true }).catch(() => {
      // best effort on window close
    });
  });
})();
