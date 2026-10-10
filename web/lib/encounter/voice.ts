// Optional voice. Speech out: /api/tts audio when the server returns 200, otherwise the browser's SpeechSynthesis.
// Speech in: the browser's SpeechRecognition when it exists. Everything degrades to plain text.
import { encApi } from "./api";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyWin = any;

export const canSpeak = () => typeof window !== "undefined" && "speechSynthesis" in window;
export const canListen = () => typeof window !== "undefined" && !!((window as AnyWin).SpeechRecognition || (window as AnyWin).webkitSpeechRecognition);

let serverTts: boolean | null = null; // null = not tried yet
let audio: HTMLAudioElement | null = null;

export function stopSpeaking() {
  try {
    audio?.pause();
    audio = null;
    if (canSpeak()) window.speechSynthesis.cancel();
  } catch {
    /* ignore */
  }
}

function pickVoice(gender?: string): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang?.toLowerCase().startsWith("en"));
  if (!voices.length) return undefined;
  const female = /female|samantha|victoria|karen|moira|tessa|zira|susan|fiona|allison|ava/i;
  const male = /\bmale|daniel|alex|fred|david|mark|tom|aaron|oliver|rishi/i;
  const g = (gender || "").toLowerCase();
  const want = g.startsWith("f") || g.startsWith("w") ? female : g.startsWith("m") ? male : null;
  return (want && voices.find((v) => want.test(v.name))) || voices.find((v) => v.default) || voices[0];
}

/** Returns which engine spoke: "server", "browser" or "none". */
export async function speak(text: string, opts: { gender?: string; voice?: string } = {}): Promise<"server" | "browser" | "none"> {
  stopSpeaking();
  if (!text.trim()) return "none";
  if (serverTts !== false) {
    const blob = await encApi.tts(text, opts.voice);
    serverTts = !!blob;
    if (blob) {
      try {
        audio = new Audio(URL.createObjectURL(blob));
        await audio.play();
        return "server";
      } catch {
        /* fall through to the browser voice */
      }
    }
  }
  if (!canSpeak()) return "none";
  try {
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice(opts.gender);
    if (v) u.voice = v;
    u.rate = 1;
    window.speechSynthesis.speak(u);
    return "browser";
  } catch {
    return "none";
  }
}

export interface Dictation {
  stop: () => void;
}
/** Starts dictation; onText gets the running transcript, onEnd fires when recognition stops. */
export function listen(onText: (text: string, final: boolean) => void, onEnd: (error?: string) => void): Dictation | null {
  const Ctor = (window as AnyWin).SpeechRecognition || (window as AnyWin).webkitSpeechRecognition;
  if (!Ctor) return null;
  try {
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e: AnyWin) => {
      let text = "";
      let final = false;
      for (let i = 0; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
        if (e.results[i].isFinal) final = true;
      }
      onText(text.trim(), final);
    };
    rec.onerror = (e: AnyWin) => onEnd(String(e?.error || "error"));
    rec.onend = () => onEnd();
    rec.start();
    return { stop: () => rec.stop() };
  } catch {
    return null;
  }
}
