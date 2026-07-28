import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { VoiceCaptureState } from "../../types";
import { secureJsonRequest } from "../../lib/secureRequest";

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0?: { transcript?: string };
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: { resultIndex: number; results: ArrayLike<SpeechRecognitionResultLike> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;
type MediaRecorderConstructor = new (stream: MediaStream) => MediaRecorder;

interface VoiceDependencies {
  speechRecognitionCtor?: SpeechRecognitionConstructor | null;
  mediaDevices?: Pick<MediaDevices, "getUserMedia"> | null;
  mediaRecorderCtor?: MediaRecorderConstructor | null;
  fetchImpl?: typeof fetch;
}

interface VoiceCaptureOptions {
  endpoint?: string;
  workspaceId?: string;
  language?: string;
  maxDurationMs?: number;
  dependencies?: VoiceDependencies;
}

function browserSpeechConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const candidate = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition ?? null;
}

function browserMediaRecorder(): MediaRecorderConstructor | null {
  return typeof MediaRecorder === "undefined" ? null : MediaRecorder;
}

function permissionMessage(error: string): string {
  if (error === "not-allowed" || error === "service-not-allowed") return "Microphone permission was not granted.";
  if (error === "no-speech") return "No speech was detected. You can try again or type the use case.";
  return "Voice recognition stopped before a transcript was produced.";
}

export function useVoiceCapture(options: VoiceCaptureOptions = {}) {
  const dependencies = options.dependencies ?? {};
  const speechCtor = Object.prototype.hasOwnProperty.call(dependencies, "speechRecognitionCtor")
    ? dependencies.speechRecognitionCtor ?? null
    : browserSpeechConstructor();
  const mediaDevices = Object.prototype.hasOwnProperty.call(dependencies, "mediaDevices")
    ? dependencies.mediaDevices ?? null
    : typeof navigator !== "undefined" ? navigator.mediaDevices : null;
  const recorderCtor = Object.prototype.hasOwnProperty.call(dependencies, "mediaRecorderCtor")
    ? dependencies.mediaRecorderCtor ?? null
    : browserMediaRecorder();
  const language = options.language ?? (typeof navigator !== "undefined" ? navigator.language : "en-US");
  const maxDurationMs = options.maxDurationMs ?? 5 * 60 * 1_000;
  const browserSupported = Boolean(speechCtor);
  const enterpriseSupported = Boolean(options.endpoint && mediaDevices?.getUserMedia && recorderCtor);
  const [state, setState] = useState<VoiceCaptureState>(browserSupported || enterpriseSupported ? "idle" : "unavailable");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [extractionMethod, setExtractionMethod] = useState("");
  const [error, setError] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const modeRef = useRef<"browser" | "enterprise" | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enterpriseCompletionRef = useRef<Promise<void> | null>(null);
  const enterpriseResolveRef = useRef<(() => void) | null>(null);

  const clearDurationTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const disposeStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    chunksRef.current = [];
  }, []);

  const startDurationTimer = useCallback((stopAction: () => void) => {
    clearDurationTimer();
    timerRef.current = setTimeout(stopAction, maxDurationMs);
  }, [clearDurationTimer, maxDurationMs]);

  const startBrowser = useCallback(() => {
    if (!speechCtor) {
      setState(enterpriseSupported ? "idle" : "unavailable");
      return;
    }
    setError("");
    setInterimTranscript("");
    setExtractionMethod(`browser speech recognition (${language})`);
    setState("requesting_permission");
    modeRef.current = "browser";
    const recognition = new speechCtor();
    recognitionRef.current = recognition;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = language;
    recognition.onstart = () => {
      setState("listening");
      startDurationTimer(() => {
        setState("stopped");
        recognition.stop();
      });
    };
    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const value = result?.[0]?.transcript?.trim() ?? "";
        if (result?.isFinal) finalText += `${value} `;
        else interimText += `${value} `;
      }
      if (finalText.trim()) setTranscript((current) => `${current} ${finalText}`.trim());
      setInterimTranscript(interimText.trim());
    };
    recognition.onerror = (event) => {
      clearDurationTimer();
      setError(permissionMessage(event.error));
      setState("error");
    };
    recognition.onend = () => {
      clearDurationTimer();
      setInterimTranscript("");
      setState((current) => current === "error" ? current : "review");
    };
    recognition.start();
  }, [clearDurationTimer, enterpriseSupported, language, speechCtor, startDurationTimer]);

  const transcribeEnterpriseRecording = useCallback(async (blob: Blob) => {
    try {
      if (!options.endpoint) throw new Error("No transcription endpoint is configured.");
      const body = new FormData();
      body.append("audio", blob, "loopos-voice.webm");
      body.append("language", language);
      body.append("workspaceId", options.workspaceId ?? "local-workspace");
      const payload = await secureJsonRequest<{ transcript?: unknown; language?: unknown; provider?: unknown }>(options.endpoint, {
        fetchImpl: dependencies.fetchImpl,
        init: { method: "POST", body },
        maxResponseBytes: 500_000,
        timeoutMs: 30_000,
      });
      if (typeof payload.transcript !== "string" || !payload.transcript.trim()) throw new Error("The transcription response did not contain text.");
      setTranscript(payload.transcript.trim());
      setInterimTranscript("");
      const provider = typeof payload.provider === "string" && payload.provider.trim() ? payload.provider.trim() : "configured endpoint";
      const transcriptLanguage = typeof payload.language === "string" && payload.language.trim() ? payload.language.trim() : language;
      setExtractionMethod(`enterprise transcription (${provider}, ${transcriptLanguage})`);
      setState("review");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Enterprise transcription failed.");
      setState("error");
    } finally {
      clearDurationTimer();
      disposeStream();
      enterpriseResolveRef.current?.();
      enterpriseResolveRef.current = null;
    }
  }, [clearDurationTimer, dependencies.fetchImpl, disposeStream, language, options.endpoint, options.workspaceId]);

  const startEnterprise = useCallback(async (consented: boolean) => {
    if (!consented) {
      setError("Consent is required before audio is sent to the configured enterprise service.");
      return;
    }
    if (!enterpriseSupported || !mediaDevices || !recorderCtor) {
      setState(browserSupported ? "idle" : "unavailable");
      return;
    }
    setError("");
    setState("requesting_permission");
    try {
      const stream = await mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      modeRef.current = "enterprise";
      chunksRef.current = [];
      const recorder = new recorderCtor(stream);
      recorderRef.current = recorder;
      enterpriseCompletionRef.current = new Promise<void>((resolve) => {
        enterpriseResolveRef.current = resolve;
      });
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        setState("transcribing");
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        void transcribeEnterpriseRecording(blob);
      };
      recorder.start();
      setState("listening");
      startDurationTimer(() => recorder.stop());
    } catch {
      disposeStream();
      setError("Microphone permission was not granted.");
      setState("error");
    }
  }, [browserSupported, disposeStream, enterpriseSupported, mediaDevices, recorderCtor, startDurationTimer, transcribeEnterpriseRecording]);

  const stop = useCallback(async () => {
    clearDurationTimer();
    if (modeRef.current === "browser" && recognitionRef.current) {
      setState("stopped");
      recognitionRef.current.stop();
      return;
    }
    if (modeRef.current === "enterprise" && recorderRef.current) {
      recorderRef.current.stop();
      await enterpriseCompletionRef.current;
    }
  }, [clearDurationTimer]);

  const reset = useCallback(() => {
    clearDurationTimer();
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    disposeStream();
    modeRef.current = null;
    setTranscript("");
    setInterimTranscript("");
    setExtractionMethod("");
    setError("");
    setState(browserSupported || enterpriseSupported ? "idle" : "unavailable");
  }, [browserSupported, clearDurationTimer, disposeStream, enterpriseSupported]);

  useEffect(() => () => {
    clearDurationTimer();
    recognitionRef.current?.abort();
    disposeStream();
  }, [clearDurationTimer, disposeStream]);

  return useMemo(() => ({
    state,
    transcript,
    interimTranscript,
    extractionMethod,
    error,
    browserSupported,
    enterpriseSupported,
    startBrowser,
    startEnterprise,
    stop,
    reset,
    setTranscript,
  }), [browserSupported, enterpriseSupported, error, extractionMethod, interimTranscript, reset, startBrowser, startEnterprise, state, stop, transcript]);
}
