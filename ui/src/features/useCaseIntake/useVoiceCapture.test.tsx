import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useVoiceCapture } from "./useVoiceCapture";

class FakeRecognition {
  static instance: FakeRecognition | null = null;
  static throwOnStart = false;
  static throwOnStop = false;
  continuous = false;
  interimResults = false;
  lang = "";
  onstart: (() => void) | null = null;
  onresult: ((event: unknown) => void) | null = null;
  onerror: ((event: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  start = vi.fn(() => {
    if (FakeRecognition.throwOnStart) throw new Error("recognition start failed");
    this.onstart?.();
  });
  stop = vi.fn(() => {
    if (FakeRecognition.throwOnStop) throw new Error("recognition stop failed");
    this.onend?.();
  });
  abort = vi.fn();

  constructor() {
    FakeRecognition.instance = this;
  }

  emit(finalText: string, interimText = "") {
    const results = [
      Object.assign([{ transcript: finalText }], { isFinal: true }),
      Object.assign([{ transcript: interimText }], { isFinal: false }),
    ];
    this.onresult?.({ resultIndex: 0, results });
  }
}

class FakeMediaRecorder {
  static instance: FakeMediaRecorder | null = null;
  static throwOnStart = false;
  static throwOnStop = false;
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  start = vi.fn(() => {
    if (FakeMediaRecorder.throwOnStart) throw new Error("recorder start failed");
  });
  stop = vi.fn(() => {
    if (FakeMediaRecorder.throwOnStop) throw new Error("recorder stop failed");
    this.ondataavailable?.({ data: new Blob(["voice"], { type: this.mimeType }) });
    this.onstop?.();
  });

  constructor(_stream: MediaStream) {
    FakeMediaRecorder.instance = this;
  }
}

describe("useVoiceCapture", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeRecognition.instance = null;
    FakeRecognition.throwOnStart = false;
    FakeRecognition.throwOnStop = false;
    FakeMediaRecorder.instance = null;
    FakeMediaRecorder.throwOnStart = false;
    FakeMediaRecorder.throwOnStop = false;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("captures final and interim browser speech, then moves to review", async () => {
    const { result } = renderHook(() =>
      useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never }, language: "en-US" }),
    );

    act(() => result.current.startBrowser());
    expect(result.current.state).toBe("listening");
    expect(FakeRecognition.instance?.lang).toBe("en-US");

    act(() => FakeRecognition.instance?.emit("Agentic claims workflow", "with approval"));
    expect(result.current.transcript).toBe("Agentic claims workflow");
    expect(result.current.interimTranscript).toBe("with approval");

    await act(async () => result.current.stop());
    expect(result.current.state).toBe("review");
    expect(FakeRecognition.instance?.stop).toHaveBeenCalledTimes(1);
  });

  it("reports permission denial and unavailable browser speech honestly", () => {
    const unsupported = renderHook(() => useVoiceCapture({ dependencies: { speechRecognitionCtor: null } }));
    expect(unsupported.result.current.browserSupported).toBe(false);
    expect(unsupported.result.current.state).toBe("unavailable");

    const denied = renderHook(() => useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never } }));
    act(() => denied.result.current.startBrowser());
    act(() => FakeRecognition.instance?.onerror?.({ error: "not-allowed" }));
    expect(denied.result.current.state).toBe("error");
    expect(denied.result.current.error).toMatch(/permission/i);
  });

  it("reports a synchronous recognition start failure without leaving a pending permission state", () => {
    FakeRecognition.throwOnStart = true;
    const { result } = renderHook(() =>
      useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never } }),
    );

    act(() => result.current.startBrowser());

    expect(result.current.state).toBe("error");
    expect(result.current.error).toBe("Voice recognition could not start. You can try again or type the use case.");
  });

  it("stops browser recognition at the configured duration limit", () => {
    const { result } = renderHook(() =>
      useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never }, maxDurationMs: 100 }),
    );
    act(() => result.current.startBrowser());
    act(() => vi.advanceTimersByTime(100));

    expect(FakeRecognition.instance?.stop).toHaveBeenCalledTimes(1);
    expect(result.current.state).toBe("review");
  });

  it("does not reopen review when reset receives a delayed recognition end event", () => {
    const { result } = renderHook(() =>
      useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never } }),
    );
    act(() => result.current.startBrowser());
    const recognition = FakeRecognition.instance;
    recognition?.abort.mockImplementation(() => {
      setTimeout(() => recognition.onend?.(), 0);
    });

    act(() => result.current.reset());
    act(() => vi.advanceTimersByTime(1));

    expect(result.current.state).toBe("idle");
    expect(result.current.transcript).toBe("");
  });

  it("requires consent before enterprise recording and disposes microphone tracks after transcription", async () => {
    vi.useRealTimers();
    const stopTrack = vi.fn();
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ transcript: "Enterprise voice transcript", provider: "tenant-service", language: "en-CA" }) });
    const { result } = renderHook(() =>
      useVoiceCapture({
        endpoint: "https://enterprise.example/transcribe",
        workspaceId: "workspace-1",
        dependencies: {
          speechRecognitionCtor: null,
          mediaDevices: { getUserMedia } as never,
          mediaRecorderCtor: FakeMediaRecorder as never,
          fetchImpl: fetchImpl as never,
        },
      }),
    );

    await act(async () => result.current.startEnterprise(false));
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(fetchImpl).not.toHaveBeenCalled();

    await act(async () => result.current.startEnterprise(true));
    expect(result.current.state).toBe("listening");
    await act(async () => result.current.stop());

    await waitFor(() => expect(result.current.state).toBe("review"));
    expect(result.current.transcript).toBe("Enterprise voice transcript");
    expect(result.current.extractionMethod).toBe("enterprise transcription (tenant-service, en-CA)");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(stopTrack).toHaveBeenCalledTimes(1);
  });

  it("fails closed when enterprise transcription returns a malformed payload", async () => {
    vi.useRealTimers();
    const stopTrack = vi.fn();
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ transcript: 42 }) });
    const { result } = renderHook(() => useVoiceCapture({
      endpoint: "https://enterprise.example/transcribe",
      dependencies: {
        speechRecognitionCtor: null,
        mediaDevices: { getUserMedia } as never,
        mediaRecorderCtor: FakeMediaRecorder as never,
        fetchImpl: fetchImpl as never,
      },
    }));

    await act(async () => result.current.startEnterprise(true));
    await act(async () => result.current.stop());
    await waitFor(() => expect(result.current.state).toBe("error"));
    expect(result.current.error).toMatch(/invalid JSON response/);
    expect(stopTrack).toHaveBeenCalledTimes(1);
  });

  it("distinguishes a recorder setup failure from microphone permission denial", async () => {
    vi.useRealTimers();
    FakeMediaRecorder.throwOnStart = true;
    const stopTrack = vi.fn();
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    const { result } = renderHook(() => useVoiceCapture({
      endpoint: "https://enterprise.example/transcribe",
      dependencies: {
        speechRecognitionCtor: null,
        mediaDevices: { getUserMedia } as never,
        mediaRecorderCtor: FakeMediaRecorder as never,
      },
    }));

    await act(async () => result.current.startEnterprise(true));

    expect(result.current.state).toBe("error");
    expect(result.current.error).toBe("Enterprise microphone recording could not start. You can try again or type the use case.");
    expect(stopTrack).toHaveBeenCalledTimes(1);
  });

  it("fails closed when browser recognition cannot stop", async () => {
    FakeRecognition.throwOnStop = true;
    const { result } = renderHook(() =>
      useVoiceCapture({ dependencies: { speechRecognitionCtor: FakeRecognition as never } }),
    );

    act(() => result.current.startBrowser());
    await act(async () => result.current.stop());

    expect(result.current.state).toBe("error");
    expect(result.current.error).toBe("Voice recognition could not stop. You can try again or type the use case.");
  });

  it("fails closed when the enterprise recorder cannot stop and resolves completion", async () => {
    vi.useRealTimers();
    FakeMediaRecorder.throwOnStop = true;
    const stopTrack = vi.fn();
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    const { result } = renderHook(() => useVoiceCapture({
      endpoint: "https://enterprise.example/transcribe",
      dependencies: {
        speechRecognitionCtor: null,
        mediaDevices: { getUserMedia } as never,
        mediaRecorderCtor: FakeMediaRecorder as never,
      },
    }));

    await act(async () => result.current.startEnterprise(true));
    await act(async () => result.current.stop());

    expect(result.current.state).toBe("error");
    expect(result.current.error).toBe("Enterprise microphone recording could not stop. You can try again or type the use case.");
    expect(stopTrack).toHaveBeenCalledTimes(1);
  });
});
