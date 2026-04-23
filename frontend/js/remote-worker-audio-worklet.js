class SstRemoteWorkerAudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const processorOptions = options?.processorOptions || {};
    const chunkSizeCandidate = Number(processorOptions.chunkSize || 2048);
    this.chunkSize = Number.isFinite(chunkSizeCandidate) && chunkSizeCandidate > 0 ? Math.floor(chunkSizeCandidate) : 2048;
    this.buffer = new Float32Array(this.chunkSize);
    this.bufferWriteIndex = 0;

    this.monoSqSum = 0;
    this.ch0SqSum = 0;
    this.ch1SqSum = 0;
    this.monoSampleCount = 0;
  }

  resetChunkStats() {
    this.monoSqSum = 0;
    this.ch0SqSum = 0;
    this.ch1SqSum = 0;
    this.monoSampleCount = 0;
  }

  emitChunk() {
    if (this.bufferWriteIndex <= 0) return;
    const frame = this.buffer.slice(0, this.bufferWriteIndex);
    const sampleCount = Math.max(1, this.monoSampleCount);
    const monoRms = Math.sqrt(this.monoSqSum / sampleCount);
    const ch0Rms = Math.sqrt(this.ch0SqSum / sampleCount);
    const ch1Rms = Math.sqrt(this.ch1SqSum / sampleCount);
    const chMaxRms = Math.max(ch0Rms, ch1Rms);

    this.port.postMessage(
      {
        type: "audio-frame",
        samples: frame,
        sampleRate,
        monoRms,
        ch0Rms,
        ch1Rms,
        chMaxRms,
      },
      [frame.buffer]
    );

    this.bufferWriteIndex = 0;
    this.resetChunkStats();
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length <= 0) {
      return true;
    }
    const channelCount = input.length;
    const frameLength = input[0]?.length || 0;
    if (frameLength <= 0) {
      return true;
    }

    for (let i = 0; i < frameLength; i += 1) {
      let mixed = 0;
      for (let c = 0; c < channelCount; c += 1) {
        const channel = input[c];
        mixed += channel ? Number(channel[i] || 0) : 0;
      }
      mixed /= Math.max(1, channelCount);

      const ch0 = input[0] ? Number(input[0][i] || 0) : 0;
      const ch1 = channelCount > 1 && input[1] ? Number(input[1][i] || 0) : 0;

      this.monoSqSum += mixed * mixed;
      this.ch0SqSum += ch0 * ch0;
      this.ch1SqSum += ch1 * ch1;
      this.monoSampleCount += 1;

      this.buffer[this.bufferWriteIndex] = mixed;
      this.bufferWriteIndex += 1;
      if (this.bufferWriteIndex >= this.chunkSize) {
        this.emitChunk();
      }
    }

    return true;
  }
}

registerProcessor("sst-remote-worker-audio-processor", SstRemoteWorkerAudioProcessor);
