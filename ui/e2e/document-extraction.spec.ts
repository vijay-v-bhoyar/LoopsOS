import { expect, test, type Page } from "@playwright/test";

const binaryBrief = "# Agentic production regulated pilot claims workflow using AI agents.";

function pdfFixture(text: string): Buffer {
  const escaped = text.replace(/[\\()]/g, "\\$&");
  const stream = `BT /F1 18 Tf 72 720 Td (${escaped}) Tj ET`;
  const bodies = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${Buffer.byteLength(stream, "latin1")} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  const chunks = [Buffer.from("%PDF-1.4\n", "latin1")];
  const offsets = [0];
  for (const [index, body] of bodies.entries()) {
    offsets.push(Buffer.concat(chunks).length);
    chunks.push(Buffer.from(`${index + 1} 0 obj\n${body}\nendobj\n`, "latin1"));
  }
  const xrefOffset = Buffer.concat(chunks).length;
  const xref = [
    `xref\n0 ${bodies.length + 1}`,
    "0000000000 65535 f ",
    ...offsets.slice(1).map((offset) => `${offset.toString().padStart(10, "0")} 00000 n `),
  ].join("\n");
  chunks.push(Buffer.from(`${xref}\ntrailer\n<< /Size ${bodies.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`, "latin1"));
  return Buffer.concat(chunks);
}

function crc32(value: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of value) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function docxFixture(text: string): Buffer {
  const xmlText = text.replace(/[&<>\"]|'/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[character] ?? character));
  const files = [
    ["[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`],
    ["_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`],
    ["word/document.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>${xmlText}</w:t></w:r></w:p><w:sectPr/></w:body></w:document>`],
  ].map(([name, value]) => ({ name, data: Buffer.from(value, "utf8") }));
  const localChunks: Buffer[] = [];
  const centralChunks: Buffer[] = [];
  let offset = 0;
  for (const file of files) {
    const name = Buffer.from(file.name, "utf8");
    const checksum = crc32(file.data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(checksum, 14);
    local.writeUInt32LE(file.data.length, 18);
    local.writeUInt32LE(file.data.length, 22);
    local.writeUInt16LE(name.length, 26);
    localChunks.push(local, name, file.data);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt32LE(checksum, 16);
    central.writeUInt32LE(file.data.length, 20);
    central.writeUInt32LE(file.data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    centralChunks.push(central, name);
    offset += local.length + name.length + file.data.length;
  }
  const centralDirectory = Buffer.concat(centralChunks);
  const localDirectory = Buffer.concat(localChunks);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(centralDirectory.length, 12);
  end.writeUInt32LE(localDirectory.length, 16);
  return Buffer.concat([localDirectory, centralDirectory, end]);
}

async function openDocumentIntake(page: Page) {
  await page.addInitScript(() => window.localStorage.clear());
  await page.goto("/");
  await page.getByRole("button", { name: "Enter Evaluation Workspace" }).click();
  await page.getByRole("button", { name: "Open Use Case Advisor" }).click();
  await page.getByRole("tab", { name: "Document" }).click();
}

test("extracts valid PDF and DOCX files through the real browser workers", async ({ page }) => {
  await openDocumentIntake(page);

  await page.getByLabel("Choose documents").setInputFiles([
    { name: "live-report.pdf", mimeType: "application/pdf", buffer: pdfFixture(binaryBrief) },
    {
      name: "live-brief.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: docxFixture(binaryBrief),
    },
  ]);

  const dialog = page.getByRole("dialog", { name: "Review proposed use case" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("live-report.pdf");
  expect(await dialog.locator("input").evaluateAll((elements) => elements.map((element) => (element as HTMLInputElement).value))).toContain("Agentic AI");
  await expect(dialog).toContainText("claims workflow");
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("live-brief.docx");
  expect(await dialog.locator("input").evaluateAll((elements) => elements.map((element) => (element as HTMLInputElement).value))).toContain("Agentic AI");
  await expect(dialog).toContainText("claims workflow");
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  await expect(dialog).not.toBeVisible();
  if ((page.viewportSize()?.width ?? 1_440) < 1_280) {
    await page.getByRole("button", { name: "Edit use case" }).click();
  }
  await expect(page.getByText(/document \/ PDF\.js worker/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove live-report.pdf" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove live-brief.docx" })).toBeVisible();
  await expect(page.getByText(/document \/ Mammoth DOCX worker/)).toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources).toEqual(expect.arrayContaining([
    expect.objectContaining({ label: "live-report.pdf", extraction_method: "PDF.js worker", accepted_text: expect.stringContaining("Agentic production") }),
    expect.objectContaining({ label: "live-brief.docx", extraction_method: "Mammoth DOCX worker", accepted_text: expect.stringContaining("Agentic production") }),
  ]));
});

test("extracts local documents within limits, retains truncation warnings, and surfaces actionable failures", async ({ page }, testInfo) => {
  await openDocumentIntake(page);

  const chooser = page.getByLabel("Choose documents");
  await chooser.setInputFiles({
    name: "enterprise-agentic-readiness.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Agentic readiness\n" + "x".repeat(50_200)),
  });

  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).toBeVisible();
  await page.getByRole("button", { name: "Apply selected fields" }).click();

  const result = page.getByRole("region", { name: "Loop recommendations" });
  await expect(result).toBeVisible();
  if ((page.viewportSize()?.width ?? 1_440) < 1_280) {
    await page.getByRole("button", { name: "Edit use case" }).click();
  }

  await expect(page.getByRole("button", { name: "Remove enterprise-agentic-readiness.md" })).toBeVisible();
  await expect(page.getByText("Text was limited to 50,000 characters.")).toBeVisible();
  await expect(page.getByText(/document \/ browser text reader \/ 50,000 characters/)).toBeVisible();

  await chooser.setInputFiles({
    name: "spoofed.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("not actually a pdf"),
  });
  await expect(page.locator("p", { hasText: "The file contents do not match the .pdf format." })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Review proposed use case" })).not.toBeVisible();

  const stored = await page.evaluate(() => JSON.parse(window.localStorage.getItem("loopos.v2.workspace-state") ?? "{}"));
  expect(stored.workspaces[0].input_sources).toHaveLength(1);
  expect(stored.workspaces[0].input_sources[0]).toMatchObject({
    kind: "document",
    label: "enterprise-agentic-readiness.md",
    status: "accepted",
    extraction_method: "browser text reader",
    truncated: true,
  });
  expect(stored.workspaces[0].input_sources[0].warnings).toEqual(
    expect.arrayContaining([expect.objectContaining({ code: "truncated" })]),
  );

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("document-extraction.png"), fullPage: true });
});
