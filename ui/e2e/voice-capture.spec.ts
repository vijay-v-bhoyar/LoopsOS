import { expect, test, type Page } from "@playwright/test";

const voiceBrief = "Agentic claims triage with human approval and audit evidence.";

async function openVoiceIntake(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("tab", { name: "Voice" }).click();
}

async function installEnterpriseVoiceRuntime(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { transcriptionEndpoint: "/api/mock-transcription" };

    const stats = { getUserMediaCalls: 0, stoppedTracks: 0 };
    class FakeMediaRecorder {
      mimeType = "audio/webm";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;

      constructor(_stream: MediaStream) {}

      start() {}

      stop() {
        this.ondataavailable?.({ data: new Blob(["enterprise audio"], { type: this.mimeType }) });
        this.onstop?.();
      }
    }

    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: FakeMediaRecorder });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: async () => {
          stats.getUserMediaCalls += 1;
          return { getTracks: () => [{ stop: () => { stats.stoppedTracks += 1; } }] } as unknown as MediaStream;
        },
      },
    });
    // @ts-expect-error test hook
    window.__enterpriseVoiceStats = stats;
  });
}

test("honestly shows browser voice capability and disclosure in the current environment", async ({ page }, testInfo) => {
  await page.addInitScript(() => window.localStorage.clear());
  await openVoiceIntake(page);

  await expect(page.getByText("Browser speech recognition may use your browser vendor's configured speech service. Review the transcript before applying it.")).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Voice state: Idle");
  await expect(page.getByRole("button", { name: "Start dictation" })).toBeVisible();
  await expect(page.getByText("Voice input is unavailable in this browser and no enterprise transcription endpoint is configured.")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-unavailable.png"), fullPage: true });
});

test("shows browser speech state, transcript review, and review gating before applying voice input", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();

    class FakeSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onstart = null;
      onresult = null;
      onerror = null;
      onend = null;

      start() {
        this.onstart?.();
      }

      stop() {
        this.onend?.();
      }

      abort() {}
    }

    const speechState: { instance: InstanceType<typeof FakeSpeechRecognition> | null } = { instance: null };
    // @ts-expect-error test hook
    window.SpeechRecognition = class extends FakeSpeechRecognition {
      constructor() {
        super();
        speechState.instance = this;
      }
    };
    // @ts-expect-error test hook
    window.__emitVoiceResult = (finalText: string, interimText = "") => {
      speechState.instance?.onresult?.({
        resultIndex: 0,
        results: [
          Object.assign([{ transcript: finalText }], { isFinal: true }),
          Object.assign([{ transcript: interimText }], { isFinal: false }),
        ],
      });
    };
  });

  await openVoiceIntake(page);

  await expect(page.getByRole("status")).toHaveText("Voice state: Idle");
  await expect(page.getByRole("button", { name: "Start dictation" })).toBeVisible();
  await page.getByRole("button", { name: "Start dictation" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Listening");

  await page.evaluate((text) => {
    // @ts-expect-error test hook
    window.__emitVoiceResult(text, "with guardrails");
  }, voiceBrief);

  await expect(page.getByText(voiceBrief)).toBeVisible();
  await expect(page.getByText("with guardrails")).toBeVisible();
  await page.getByRole("button", { name: "Stop dictation" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Transcript ready for review");
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeEnabled();
  await page.getByRole("button", { name: "Analyze transcript" }).click();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await expect(page.getByText("Select and edit fields from Voice input. Nothing is saved until you apply.")).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();
  await expect(page.getByRole("region", { name: "Loop recommendations" })).toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({
    kind: "voice",
    label: "Voice input",
    status: "accepted",
  });

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-browser-review.png"), fullPage: true });
});

test("reset cancels browser recognition without reopening transcript review", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    class ResettableSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        this.onstart?.();
      }

      stop() {
        this.onend?.();
      }

      abort() {
        setTimeout(() => this.onend?.(), 0);
      }
    }
    // @ts-expect-error test hook
    window.SpeechRecognition = ResettableSpeechRecognition;
  });

  await openVoiceIntake(page);
  await page.getByRole("button", { name: "Start dictation" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Listening");
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Idle");
  await page.waitForTimeout(50);
  await expect(page.getByRole("status")).toHaveText("Voice state: Idle");
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-reset.png"), fullPage: true });
});

test("reports a synchronous browser recognition start failure without crashing the intake", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    class FailingSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        throw new Error("recognition start failed");
      }

      stop() {}

      abort() {}
    }
    // @ts-expect-error test hook
    window.SpeechRecognition = FailingSpeechRecognition;
  });

  await openVoiceIntake(page);
  await page.getByRole("button", { name: "Start dictation" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Voice input error");
  await expect(page.getByText("Voice recognition could not start. You can try again or type the use case.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-start-failure.png"), fullPage: true });
});

test("reports a browser recognition stop failure without leaving the intake stopping", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    class StopFailingSpeechRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        this.onstart?.();
      }

      stop() {
        throw new Error("recognition stop failed");
      }

      abort() {}
    }
    // @ts-expect-error test hook
    window.SpeechRecognition = StopFailingSpeechRecognition;
  });

  await openVoiceIntake(page);
  await page.getByRole("button", { name: "Start dictation" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Listening");
  await page.getByRole("button", { name: "Stop dictation" }).click();

  await expect(page.getByRole("status")).toHaveText("Voice state: Voice input error");
  await expect(page.getByText("Voice recognition could not stop. You can try again or type the use case.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-stop-failure.png"), fullPage: true });
});

test("reports an enterprise recorder start failure without mislabeling it as permission denial", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { transcriptionEndpoint: "/api/mock-transcription" };
    class FailingMediaRecorder {
      mimeType = "audio/webm";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;

      constructor(_stream: MediaStream) {}

      start() {
        throw new Error("recorder start failed");
      }

      stop() {}
    }
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: FailingMediaRecorder });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: async () => ({ getTracks: () => [{ stop: () => undefined }] }) as unknown as MediaStream },
    });
  });

  await openVoiceIntake(page);
  await page.getByText("Send this recording to the configured enterprise transcription service.").locator("..").getByRole("checkbox").check();
  await page.getByRole("button", { name: "Record for enterprise transcription" }).click();

  await expect(page.getByRole("status")).toHaveText("Voice state: Voice input error");
  await expect(page.getByText("Enterprise microphone recording could not start. You can try again or type the use case.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-enterprise-start-failure.png"), fullPage: true });
});

test("reports an enterprise recorder stop failure without leaving the intake stopping", async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.__LOOPOS_RUNTIME_CONFIG__ = { transcriptionEndpoint: "/api/mock-transcription" };
    class StopFailingMediaRecorder {
      mimeType = "audio/webm";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;

      constructor(_stream: MediaStream) {}

      start() {}

      stop() {
        throw new Error("recorder stop failed");
      }
    }
    Object.defineProperty(window, "SpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", { configurable: true, value: undefined });
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: StopFailingMediaRecorder });
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia: async () => ({ getTracks: () => [{ stop: () => undefined }] }) as unknown as MediaStream },
    });
  });

  await openVoiceIntake(page);
  await page.getByText("Send this recording to the configured enterprise transcription service.").locator("..").getByRole("checkbox").check();
  await page.getByRole("button", { name: "Record for enterprise transcription" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Listening");
  await page.getByRole("button", { name: "Stop and transcribe" }).click();

  await expect(page.getByRole("status")).toHaveText("Voice state: Voice input error");
  await expect(page.getByText("Enterprise microphone recording could not stop. You can try again or type the use case.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-enterprise-stop-failure.png"), fullPage: true });
});

test("records through the enterprise transcription endpoint and disposes the microphone before review", async ({ page }, testInfo) => {
  await installEnterpriseVoiceRuntime(page);
  let requestCount = 0;
  await page.route("**/api/mock-transcription", async (route) => {
    requestCount += 1;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["content-type"]).toContain("multipart/form-data");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ transcript: "Enterprise claims triage with approval", provider: "tenant-transcriber", language: "en-CA" }),
    });
  });

  await openVoiceIntake(page);

  await expect(page.getByText("Send this recording to the configured enterprise transcription service.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record for enterprise transcription" })).toBeDisabled();
  await page.getByText("Send this recording to the configured enterprise transcription service.").locator("..").getByRole("checkbox").check();
  await page.getByRole("button", { name: "Record for enterprise transcription" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Listening");
  await page.getByRole("button", { name: "Stop and transcribe" }).click();
  await expect(page.getByRole("status")).toHaveText("Voice state: Transcript ready for review");
  await expect(page.getByRole("textbox", { name: "Transcript" })).toHaveValue("Enterprise claims triage with approval");
  expect(requestCount).toBe(1);

  await page.getByRole("button", { name: "Analyze transcript" }).click();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({
    kind: "voice",
    extraction_method: "enterprise transcription (tenant-transcriber, en-CA)",
    status: "accepted",
  });
  const stats = await page.evaluate(() => (window as Window & { __enterpriseVoiceStats?: { getUserMediaCalls: number; stoppedTracks: number } }).__enterpriseVoiceStats);
  expect(stats).toMatchObject({ getUserMediaCalls: 1, stoppedTracks: 1 });

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-enterprise-review.png"), fullPage: true });
});

test("fails closed when enterprise transcription returns an invalid payload", async ({ page }, testInfo) => {
  await installEnterpriseVoiceRuntime(page);
  await page.route("**/api/mock-transcription", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ transcript: 42 }),
    });
  });

  await openVoiceIntake(page);
  await page.getByText("Send this recording to the configured enterprise transcription service.").locator("..").getByRole("checkbox").check();
  await page.getByRole("button", { name: "Record for enterprise transcription" }).click();
  await page.getByRole("button", { name: "Stop and transcribe" }).click();

  await expect(page.getByRole("status")).toHaveText("Voice state: Voice input error");
  await expect(page.getByText("Enterprise endpoint returned an invalid JSON response.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze transcript" })).toBeDisabled();
  const stats = await page.evaluate(() => (window as Window & { __enterpriseVoiceStats?: { getUserMediaCalls: number; stoppedTracks: number } }).__enterpriseVoiceStats);
  expect(stats).toMatchObject({ getUserMediaCalls: 1, stoppedTracks: 1 });

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("voice-capture-enterprise-invalid-response.png"), fullPage: true });
});
