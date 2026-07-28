import { expect, test, type Page } from "@playwright/test";

const voiceBrief = "Agentic claims triage with human approval and audit evidence.";

async function openVoiceIntake(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("tab", { name: "Voice" }).click();
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
