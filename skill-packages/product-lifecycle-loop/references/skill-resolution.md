# Resolve skills before composing them

Read when selecting owners or diagnosing an unavailable or conflicting skill.
The host's current available-skills catalog and callable tools are the first
source for this session. Files on disk and plugin cache packages are a broader
inventory, not proof that the host has activated those capabilities.

## Provenance and selection

Use distinct labels:

- **Personal:** installed under a personal skill root, including custom or copied
  third-party skills such as gstack. Personal installation does not establish
  authorship or make a skill a built-in Codex capability.
- **Workspace:** a repository-specific skill, subject to its scope.
- **System:** an entry under the installed Codex system skill root.
- **Plugin:** a skill supplied by an active plugin, identified by the session's
  qualified name and version/root. A cached package may be inactive or obsolete.
- **Tool:** an actual callable Codex/app/connector capability. A skill with a
  similar name does not create the tool.

Prefer the exact skill or plugin the user named. Otherwise choose an applicable
entry from the active catalog, taking workspace scope into account. When that
catalog resolves a name to one path, use that path and record it. If multiple
active entries are equally applicable, compare the relevant instructions before
choosing; do not rely on filesystem enumeration order or newest modification time.

If a required name is absent from the catalog, search known skill roots, including
nested folders and the system root. An on-disk-only skill may be read as an
explicitly resolved local instruction source when allowed by the host; record
that status. It still cannot confer unavailable tools or plugin activation.
Do not install an unrelated plugin or claim that a recommended plugin is active.

Identical copies may share one logical owner. Different hashes require comparing
the relevant behavior and selecting a specific source. Do not silently merge
instructions, rewrite other copies, or pick whichever gives fewer gates.
User authorization and higher-priority instructions control the action; skill
wording cannot replace them. Explain a material unresolved incompatibility and
continue work that does not depend on it.

## Inventory helper

`scripts/inventory_skills.py` is a read-only discovery helper. It parses metadata
without executing scanned content and records source hashes, duplicates, errors,
and exact-name resolutions. It does not choose a trusted version, declare a
skill active, install anything, or grant release permission.

Run with a working Python 3 interpreter and actual roots discovered on this host.
Example in PowerShell, from this skill's directory:

```powershell
$skillHome = Join-Path $env:USERPROFILE '.codex/skills'
$agentSkills = Join-Path $env:USERPROFILE '.agents/skills'
python scripts/inventory_skills.py --root "personal=$skillHome" --root "personal=$agentSkills" --name codex-product-build-loop --name release-governor --output skill-inventory.json
python -m unittest discover -s scripts -p test_inventory_skills.py
```

The command assumes `python` is available; use the host's resolved runtime path
if it is not. Choose a writable output location outside the installed skill when
the package is read-only. Use repeated `--root CATEGORY=PATH` for workspace,
system, or plugin roots and label overlapping root provenance accurately.

`MATCH` means matching files exist with identical content, `AMBIGUOUS` means
different content for the same declared name, and `MISSING` means no match in the
successfully scanned files. Inspect errors before drawing an absence conclusion.
The helper's category is supplied by the caller; it is not a security attestation.

## Names from the original map

Exact-name lookup matters. `deep-research`, document skills, browser QA, design,
and data visualization may be plugin-qualified in the current host. Use the
qualified catalog entry and its actual source, not a guessed slash command.

Do not assume `claude-api`, `frontend-design`, `dataviz`, `artifact-design`,
`verify`, `code-review`, `simplify`, `init`, `session-start-hook`, `update-config`,
or `loop` are Codex system skills. Resolve them. The lifecycle map supplies
capability-level alternatives when appropriate; alternatives are not aliases.

The September 2026 authoring audit also found `supabase-architect`,
`supabase-dexie-sync`, `tool-contracts`, `test-hardening`, `stakeholder-brief`,
`web-artifacts-builder`, and `xlsx` on disk even though they were omitted from the
session's skill list. This is a discovery reminder, not an availability promise:
refresh the inventory on the target machine before using them.
