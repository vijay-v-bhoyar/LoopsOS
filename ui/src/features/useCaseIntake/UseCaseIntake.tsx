import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import { FileText, LoaderCircle, Mic, RotateCcw, Square, Trash2, Type, Upload, WandSparkles, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { Button } from "../../components/Button";
import { HelpPopover, InlineNote } from "../../components/Help";
import { llmEndpoint, transcriptionEndpoint } from "../../lib/runtimeConfig";
import { nowIso, uid } from "../../lib/workspaceStore";
import type { UseCaseDraft, UseCaseInput, UseCaseSource } from "../../types";
import { extractDocument, INTAKE_LIMITS, IntakeError } from "./documentExtraction";
import { applyUseCaseDraft, enhanceUseCaseProposal, proposeUseCaseFields } from "./fieldProposal";
import { useVoiceCapture } from "./useVoiceCapture";

const FIELD_LABELS: Record<keyof UseCaseInput, string> = {
  title: "Use-case title",
  description: "Workflow and problem",
  environment: "Environment",
  aiScope: "AI scope",
  dataSensitivity: "Data sensitivity",
  businessOutcome: "Business outcome",
  maturity: "Maturity",
  constraints: "Constraints",
};

const VOICE_STATE_LABELS = {
  idle: "Idle",
  requesting_permission: "Requesting microphone permission",
  listening: "Listening",
  stopped: "Stopping",
  transcribing: "Transcribing with the configured enterprise service",
  review: "Transcript ready for review",
  unavailable: "Unavailable",
  error: "Voice input error",
} as const;

function createTextSource(
  kind: "text" | "voice",
  label: string,
  text: string,
  currentWorkspaceCharacters: number,
  extractionMethod?: string,
): UseCaseSource {
  const remaining = Math.max(0, INTAKE_LIMITS.maxWorkspaceCharacters - currentWorkspaceCharacters);
  const retained = text.trim().slice(0, Math.min(INTAKE_LIMITS.maxSourceCharacters, remaining));
  const truncated = retained.length < text.trim().length;
  return {
    source_id: uid("source"),
    kind,
    label,
    mime_type: "text/plain",
    status: "ready_for_review",
    accepted_text: retained,
    extraction_method: extractionMethod ?? (kind === "voice" ? "speech transcript" : "typed text"),
    character_count: retained.length,
    created_at: nowIso(),
    warnings: truncated ? [{ code: "truncated", message: `Text was limited to ${retained.length.toLocaleString()} characters.` }] : [],
    truncated,
  };
}

export function UseCaseIntake({
  input,
  sources,
  workspaceId,
  onApply,
  onRemoveSource,
}: {
  input: UseCaseInput;
  sources: UseCaseSource[];
  workspaceId: string;
  onApply: (source: UseCaseSource, nextInput: UseCaseInput) => void;
  onRemoveSource: (sourceId: string) => void;
}) {
  const [typedText, setTypedText] = useState("");
  const [activeSource, setActiveSource] = useState<UseCaseSource | null>(null);
  const [draft, setDraft] = useState<UseCaseDraft | null>(null);
  const [selectedFields, setSelectedFields] = useState<Set<keyof UseCaseInput>>(new Set());
  const [queuedSources, setQueuedSources] = useState<UseCaseSource[]>([]);
  const [processing, setProcessing] = useState(false);
  const [enhancing, setEnhancing] = useState(false);
  const [message, setMessage] = useState("");
  const [enterpriseConsent, setEnterpriseConsent] = useState(false);
  const reviewTriggerRef = useRef<HTMLElement | null>(null);
  const acceptedCharacters = useMemo(() => sources.reduce((total, source) => total + source.character_count, 0), [sources]);
  const documentCount = sources.filter((source) => source.kind === "document").length;
  const llmServiceEndpoint = llmEndpoint();
  const transcriptionServiceEndpoint = transcriptionEndpoint();
  const voice = useVoiceCapture({ endpoint: transcriptionServiceEndpoint, workspaceId });

  const activateSource = useCallback((source: UseCaseSource) => {
    const nextDraft = proposeUseCaseFields(source, input);
    setActiveSource(source);
    setDraft(nextDraft);
    setSelectedFields(new Set(nextDraft.fields.map((field) => field.field)));
    setMessage(`${source.label} is ready for review.`);
  }, [input]);

  const advanceQueue = useCallback(() => {
    const [next, ...rest] = queuedSources;
    setQueuedSources(rest);
    if (next) activateSource(next);
    else {
      setActiveSource(null);
      setDraft(null);
      setSelectedFields(new Set());
    }
  }, [activateSource, queuedSources]);

  const analyzeTypedText = () => {
    if (!typedText.trim()) return;
    const source = createTextSource("text", "Typed use case", typedText, acceptedCharacters);
    if (!source.accepted_text) {
      setMessage("The workspace input-source text limit has been reached.");
      return;
    }
    activateSource(source);
  };

  const handleDocuments = async (files: File[]) => {
    if (!files.length) return;
    setProcessing(true);
    setMessage("Reading documents locally.");
    const extracted: UseCaseSource[] = [];
    let runningCharacters = acceptedCharacters;
    try {
      for (const file of files) {
        const source = await extractDocument(file, {
          currentFileCount: documentCount + extracted.length,
          currentWorkspaceCharacters: runningCharacters,
        });
        extracted.push(source);
        runningCharacters += source.character_count;
      }
      const [first, ...rest] = extracted;
      setQueuedSources(rest);
      if (first) activateSource(first);
    } catch (reason) {
      setMessage(reason instanceof IntakeError ? reason.message : "The document could not be read.");
    } finally {
      setProcessing(false);
    }
  };

  const analyzeVoice = () => {
    if (!voice.transcript.trim()) return;
    const source = createTextSource("voice", "Voice input", voice.transcript, acceptedCharacters, voice.extractionMethod);
    if (!source.accepted_text) {
      setMessage("The workspace input-source text limit has been reached.");
      return;
    }
    activateSource(source);
  };

  const applyDraft = () => {
    if (!activeSource || !draft) return;
    const nextInput = applyUseCaseDraft(input, draft, selectedFields);
    onApply({ ...activeSource, status: "accepted" }, nextInput);
    if (activeSource.kind === "text") setTypedText("");
    if (activeSource.kind === "voice") voice.reset();
    setMessage(`${activeSource.label} was accepted. Recommendations now include this source.`);
    advanceQueue();
  };

  const enhanceDraft = async () => {
    if (!activeSource || !draft || !llmServiceEndpoint) return;
    setEnhancing(true);
    const enhanced = await enhanceUseCaseProposal(activeSource, input, draft, { endpoint: llmServiceEndpoint });
    setDraft(enhanced);
    setSelectedFields(new Set(enhanced.fields.map((field) => field.field)));
    setEnhancing(false);
    setMessage(enhanced.method === "enterprise LLM" ? "Enterprise AI suggestions are ready for review." : "Enterprise AI was unavailable. Deterministic suggestions were preserved.");
  };

  const updateDraftValue = (field: keyof UseCaseInput, value: string) => {
    setDraft((current) => current ? { ...current, fields: current.fields.map((proposal) => proposal.field === field ? { ...proposal, value } : proposal) } : current);
  };

  return (
    <div className="mb-5 border-b border-border2 pb-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-fg1">Multimodal intake</h3>
          <p className="mt-1 text-sm text-fg2">Describe the use case, attach a document, or dictate it. Nothing changes until you review and apply the proposed fields.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs text-fg3">{sources.length} retained source{sources.length === 1 ? "" : "s"}</div>
          <HelpPopover helpKey="multimodalIntake" />
        </div>
      </div>

      <Tabs.Root defaultValue="describe">
        <Tabs.List className="control-muted mb-4 grid w-full grid-cols-3 p-1" aria-label="Use case input method">
          <IntakeTab value="describe" label="Describe" icon={<Type className="h-4 w-4" aria-hidden="true" />} />
          <IntakeTab value="document" label="Document" icon={<FileText className="h-4 w-4" aria-hidden="true" />} />
          <IntakeTab value="voice" label="Voice" icon={<Mic className="h-4 w-4" aria-hidden="true" />} />
        </Tabs.List>

        <Tabs.Content value="describe" className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-fg1">Describe the use case</span>
            <textarea
              className="control min-h-32 w-full px-3 py-2 text-sm"
              value={typedText}
              onChange={(event) => setTypedText(event.target.value)}
              placeholder="Describe the workflow, business outcome, environment, risks, and constraints."
            />
          </label>
          <Button variant="primary" onClick={(event) => { reviewTriggerRef.current = event.currentTarget; analyzeTypedText(); }} disabled={!typedText.trim()}>
            <WandSparkles className="h-4 w-4" aria-hidden="true" />
            Analyze and review
          </Button>
        </Tabs.Content>

        <Tabs.Content value="document" className="space-y-3">
          <label
            className="control-muted flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 border-dashed px-4 py-5 text-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              reviewTriggerRef.current = event.currentTarget;
              void handleDocuments(Array.from(event.dataTransfer.files));
            }}
          >
            <Upload className="h-5 w-5 text-brand" aria-hidden="true" />
            <span className="text-sm font-semibold text-fg1">Choose documents</span>
            <span className="text-xs text-fg3">PDF, DOCX, TXT, or Markdown. Up to five files, 10 MB each.</span>
            <input
              className="sr-only"
              type="file"
              aria-label="Choose documents"
              multiple
              accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                reviewTriggerRef.current = event.currentTarget;
                event.currentTarget.value = "";
                void handleDocuments(files);
              }}
            />
          </label>
          {processing ? <div className="flex items-center gap-2 text-sm text-fg2"><LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />Reading documents locally</div> : null}
          <InlineNote>Raw files stay in browser memory and are discarded after extraction. OCR is not included.</InlineNote>
        </Tabs.Content>

        <Tabs.Content value="voice" className="space-y-3">
          <InlineNote>
            Browser speech recognition may use your browser vendor's configured speech service. Review the transcript before applying it.
          </InlineNote>
          {!voice.browserSupported && !voice.enterpriseSupported ? (
            <InlineNote tone="warning">Voice input is unavailable in this browser and no enterprise transcription endpoint is configured.</InlineNote>
          ) : null}
          <div className="min-h-6 text-sm font-semibold text-fg2" role="status" aria-live="polite">
            Voice state: {VOICE_STATE_LABELS[voice.state]}
          </div>
          {voice.browserSupported ? (
            <div className="flex min-h-12 flex-wrap items-center gap-2">
              {voice.state !== "listening" ? (
                <Button className="w-full sm:w-52" variant="primary" disabled={voice.state === "requesting_permission"} onClick={voice.startBrowser}><Mic className="h-4 w-4" aria-hidden="true" />Start dictation</Button>
              ) : (
                <Button className="w-full sm:w-52" onClick={() => void voice.stop()}><Square className="h-4 w-4" aria-hidden="true" />Stop dictation</Button>
              )}
              <Button variant="ghost" onClick={voice.reset}><RotateCcw className="h-4 w-4" aria-hidden="true" />Reset</Button>
            </div>
          ) : null}
          {!voice.browserSupported && voice.enterpriseSupported ? (
            <div className="space-y-3">
              <label className="flex items-start gap-2 text-sm text-fg2">
                <input type="checkbox" checked={enterpriseConsent} onChange={(event) => setEnterpriseConsent(event.target.checked)} />
                <span>Send this recording to the configured enterprise transcription service.</span>
              </label>
              {voice.state !== "listening" ? (
                <Button className="w-full sm:w-72" variant="primary" disabled={!enterpriseConsent || voice.state === "requesting_permission" || voice.state === "transcribing"} onClick={() => void voice.startEnterprise(enterpriseConsent)}><Mic className="h-4 w-4" aria-hidden="true" />Record for enterprise transcription</Button>
              ) : (
                <Button className="w-full sm:w-72" onClick={() => void voice.stop()}><Square className="h-4 w-4" aria-hidden="true" />Stop and transcribe</Button>
              )}
            </div>
          ) : null}
          {voice.error ? <InlineNote tone="critical">{voice.error}</InlineNote> : null}
          {voice.transcript || voice.interimTranscript ? (
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-fg1">Transcript</span>
              {voice.state === "listening" ? (
                <div className="control min-h-28 w-full px-3 py-2 text-sm" aria-live="polite">
                  {voice.transcript} {voice.interimTranscript ? <span className="text-fg3">{voice.interimTranscript}</span> : null}
                </div>
              ) : (
                <textarea className="control min-h-28 w-full px-3 py-2 text-sm" value={voice.transcript} onChange={(event) => voice.setTranscript(event.target.value)} />
              )}
            </label>
          ) : null}
          <Button variant="primary" onClick={(event) => { reviewTriggerRef.current = event.currentTarget; analyzeVoice(); }} disabled={!voice.transcript.trim() || voice.state === "listening" || voice.state === "transcribing"}>
            <WandSparkles className="h-4 w-4" aria-hidden="true" />
            Analyze transcript
          </Button>
        </Tabs.Content>
      </Tabs.Root>

      <div className="sr-only" aria-live="polite">{message}</div>
      {message ? <p className="mt-3 text-sm text-fg2">{message}</p> : null}

      {sources.length ? (
        <div className="mt-5 border-t border-border2 pt-4">
          <div className="mb-2 text-sm font-semibold text-fg1">Input sources</div>
          <div className="divide-y divide-border2">
            {sources.map((source) => (
              <div key={source.source_id} className="flex items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="break-words text-sm font-semibold text-fg1">{source.label}</div>
                  <div className="mt-1 text-xs text-fg3">{source.kind} / {source.extraction_method} / {source.character_count.toLocaleString()} characters</div>
                  {source.warnings.map((warning) => <div key={`${source.source_id}-${warning.code}-${warning.message}`} className="mt-1 text-xs text-warning">{warning.message}</div>)}
                </div>
                <button className="inline-flex min-h-9 min-w-9 shrink-0 items-center justify-center rounded-control text-fg3 hover:bg-bg2" aria-label={`Remove ${source.label}`} onClick={() => onRemoveSource(source.source_id)}>
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-fg3">Removing a source changes future matches but does not revert fields you already approved.</p>
        </div>
      ) : null}

      <Dialog.Root open={Boolean(activeSource && draft)} onOpenChange={(open) => { if (!open) advanceQueue(); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-fg1/50" />
          <Dialog.Content
            className="surface fixed inset-x-3 bottom-3 top-3 z-50 mx-auto flex max-w-4xl flex-col overflow-hidden p-0"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              reviewTriggerRef.current?.focus();
            }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-border2 px-5 py-4">
              <div>
                <Dialog.Title className="text-xl font-semibold text-fg1">Review proposed use case</Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-fg2">Select and edit fields from {activeSource?.label}. Nothing is saved until you apply.</Dialog.Description>
              </div>
              <Dialog.Close asChild>
                <button className="inline-flex min-h-9 min-w-9 items-center justify-center rounded-control text-fg3 hover:bg-bg2" aria-label="Discard proposal"><X className="h-4 w-4" aria-hidden="true" /></button>
              </Dialog.Close>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-4">
              <div className="divide-y divide-border2">
                {draft?.fields.map((proposal) => (
                  <div key={proposal.field} className="grid gap-3 py-4 lg:grid-cols-[12rem_1fr]">
                    <label className="flex items-start gap-2 text-sm font-semibold text-fg1">
                      <input
                        type="checkbox"
                        checked={selectedFields.has(proposal.field)}
                        onChange={(event) => setSelectedFields((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(proposal.field);
                          else next.delete(proposal.field);
                          return next;
                        })}
                        aria-label={`Apply ${FIELD_LABELS[proposal.field]}`}
                      />
                      <span>{FIELD_LABELS[proposal.field]}</span>
                    </label>
                    <div className="space-y-2">
                      <div className="text-xs text-fg3">Current: {input[proposal.field] || "Not provided"}</div>
                      {proposal.field === "description" || proposal.field === "businessOutcome" || proposal.field === "constraints" ? (
                        <textarea className="control min-h-20 w-full px-3 py-2 text-sm" value={proposal.value} onChange={(event) => updateDraftValue(proposal.field, event.target.value)} />
                      ) : (
                        <input className="control min-h-10 w-full px-3 text-sm" value={proposal.value} onChange={(event) => updateDraftValue(proposal.field, event.target.value)} />
                      )}
                      <div className="text-xs text-fg3">{proposal.method}: {proposal.evidence_excerpt}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border2 bg-bg2 px-5 py-4">
              <div className="text-xs text-fg3">{selectedFields.size} of {draft?.fields.length ?? 0} fields selected</div>
              <div className="flex flex-wrap gap-2">
                {llmServiceEndpoint ? (
                  <Button onClick={() => void enhanceDraft()} disabled={enhancing}>
                    {enhancing ? <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" /> : <WandSparkles className="h-4 w-4" aria-hidden="true" />}
                    Enhance with enterprise AI
                  </Button>
                ) : null}
                <Dialog.Close asChild><Button variant="ghost">Discard</Button></Dialog.Close>
                <Button variant="primary" onClick={applyDraft} disabled={!selectedFields.size}>Apply selected fields</Button>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function IntakeTab({ value, label, icon }: { value: string; label: string; icon: React.ReactNode }) {
  return (
    <Tabs.Trigger value={value} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-control px-3 text-sm font-semibold text-fg2 hover:bg-bg1 data-[state=active]:bg-bg1 data-[state=active]:text-brand data-[state=active]:shadow-card">
      {icon}
      {label}
    </Tabs.Trigger>
  );
}
