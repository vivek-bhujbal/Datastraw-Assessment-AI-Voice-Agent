export function makeWav(frames: Float32Array[], rate: number) {
  const count = frames.reduce((sum, frame) => sum + frame.length, 0);
  const data = new ArrayBuffer(44 + count * 2);
  const view = new DataView(data);
  const write = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + count * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, count * 2, true);
  let offset = 44;
  for (const frame of frames) {
    for (const sample of frame) {
      const value = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, Math.round(value * (value < 0 ? 32768 : 32767)), true);
      offset += 2;
    }
  }
  return data;
}

export class CallAudio {
  private context: AudioContext;
  private stream: MediaStream | null = null;
  private mic: AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private gain: GainNode | null = null;
  private stopped = false;
  private listening = false;
  private cooldown = 0;
  private frames: Float32Array[] = [];
  private preroll: Float32Array[] = [];
  private speaking = false;
  private elapsed = 0;
  private voiced = 0;
  private silence = 0;
  private nodes = new Set<AudioBufferSourceNode>();
  private nextTime = 0;
  private chunk: string | null = null;
  private complete = false;
  private odd: number | null = null;
  private samples = 0;

  constructor(
    private onTurn: (data: ArrayBuffer) => void,
    private onPlayed: (id: string, success: boolean) => void,
    private onLevel: (level: number) => void,
    private onSpeaking: () => void,
    private onError: (message: string) => void,
  ) {
    this.context = new AudioContext();
    // Resume during the button click, before microphone permission interrupts it.
    void this.context.resume().catch(() => this.onError("Your browser blocked audio playback. Start a new call and allow audio."));
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia || !this.context.audioWorklet) {
      throw new Error("Voice calls need a supported browser on HTTPS or localhost.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    if (this.stopped) {
      stream.getTracks().forEach(track => track.stop());
      return;
    }
    this.stream = stream;
    stream.getAudioTracks()[0].onended = () => {
      if (!this.stopped) this.onError("The microphone was disconnected. Please end the call and reconnect it.");
    };
    await this.context.audioWorklet.addModule("/mic-worklet.js");
    if (this.stopped) return;
    this.source = this.context.createMediaStreamSource(stream);
    this.mic = new AudioWorkletNode(this.context, "mic-processor");
    this.gain = this.context.createGain();
    this.gain.gain.value = 0;
    this.source.connect(this.mic).connect(this.gain).connect(this.context.destination);
    this.mic.port.onmessage = event => this.capture(event.data as Float32Array);
    if (this.context.state !== "running") throw new Error("Browser audio is paused. Allow audio playback and start a new call.");
  }

  setListening(value: boolean) {
    this.listening = value;
    this.resetInput();
    if (value) this.cooldown = performance.now() + 300;
  }

  private resetInput() {
    this.frames = [];
    this.preroll = [];
    this.speaking = false;
    this.elapsed = this.voiced = this.silence = 0;
    this.onLevel(0);
  }

  private capture(frame: Float32Array) {
    if (!this.listening || this.stopped || performance.now() < this.cooldown) return;
    const ms = frame.length / this.context.sampleRate * 1000;
    const rms = Math.sqrt(frame.reduce((sum, value) => sum + value * value, 0) / frame.length);
    this.onLevel(Math.min(1, rms * 8));
    const voice = rms > 0.018;
    if (!this.speaking) {
      this.preroll.push(frame);
      if (this.preroll.length > Math.ceil(this.context.sampleRate * 0.2 / frame.length)) this.preroll.shift();
      if (!voice) return;
      this.speaking = true;
      this.frames = this.preroll;
      this.preroll = [];
    } else {
      this.frames.push(frame);
    }
    this.elapsed += ms;
    if (voice) { this.voiced += ms; this.silence = 0; }
    else this.silence += ms;
    if (this.silence >= 900 || this.elapsed >= 20000) {
      if (this.voiced >= 180) {
        const data = makeWav(this.frames, this.context.sampleRate);
        this.setListening(false);
        this.onTurn(data);
      } else this.resetInput();
    }
  }

  beginSpeech(id: string) {
    this.setListening(false);
    this.chunk = id;
    this.complete = false;
    this.odd = null;
    this.samples = 0;
    this.nextTime = this.context.currentTime + 0.05;
  }

  play(data: ArrayBuffer) {
    if (this.stopped || !this.chunk) return;
    if (this.context.state !== "running") {
      this.onPlayed(this.chunk, false);
      this.chunk = null;
      this.onError("Audio playback was paused by the browser. Please end the call and start again.");
      return;
    }
    let bytes = new Uint8Array(data);
    if (this.odd !== null) {
      const joined = new Uint8Array(bytes.length + 1);
      joined[0] = this.odd;
      joined.set(bytes, 1);
      bytes = joined;
      this.odd = null;
    }
    if (bytes.length % 2) { this.odd = bytes[bytes.length - 1]; bytes = bytes.slice(0, -1); }
    if (!bytes.length) return;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
    const buffer = this.context.createBuffer(1, bytes.length / 2, 24000);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const node = this.context.createBufferSource();
    node.buffer = buffer;
    node.connect(this.context.destination);
    this.nodes.add(node);
    this.samples += channel.length;
    node.onended = () => { this.nodes.delete(node); node.disconnect(); this.checkDone(); };
    const start = Math.max(this.context.currentTime + 0.02, this.nextTime);
    node.start(start);
    this.nextTime = start + buffer.duration;
    this.onSpeaking();
  }

  finishSpeech(id: string) {
    if (this.chunk !== id) return;
    this.complete = true;
    this.checkDone();
  }

  private checkDone() {
    if (this.complete && this.nodes.size === 0 && this.chunk) {
      const id = this.chunk;
      this.chunk = null;
      this.onPlayed(id, this.samples > 0 && this.odd === null);
    }
  }

  stopPlayback() {
    const id = this.chunk;
    this.chunk = null;
    for (const node of this.nodes) { node.onended = null; node.stop(); node.disconnect(); }
    this.nodes.clear();
    if (id) this.onPlayed(id, false);
  }

  stop() {
    this.stopped = true;
    this.setListening(false);
    this.stopPlayback();
    this.stream?.getTracks().forEach(track => track.stop());
    this.source?.disconnect();
    if (this.mic) { this.mic.port.onmessage = null; this.mic.disconnect(); }
    this.gain?.disconnect();
    if (this.context.state !== "closed") void this.context.close();
  }
}

