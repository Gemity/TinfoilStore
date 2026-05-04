# Claude Summary Prompt Template

## Role

You are Claude Code acting in the `summarizing` phase.
Your job is to:
1. Produce a concise project summary document
2. Update the project's CLAUDE.md to reflect current state

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `summarizing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `claude`
- design_version: `{{DESIGN_VERSION}}`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`
- design_sha256: `{{DESIGN_SHA256}}`

## Inputs

Read the inline context appended below. Do NOT read files from disk for artifacts -- everything you need is in this prompt.
You MAY read the existing `CLAUDE.md` file at the project root to understand its current structure before updating it.

---

## Task 1: Write summary.md

Write `.ai-loop/artifacts/current/summary.md` with YAML frontmatter and the required sections.

### Frontmatter format

```yaml
---
artifact_type: summary
artifact_version: 1
run_id: {{RUN_ID}}
iteration: {{ITERATION}}
phase: summarizing
phase_attempt: {{PHASE_ATTEMPT}}
producer: claude
created_at: <ISO-8601 timestamp>
---
```

### Required sections

Use level-2 headings (`##`) for each section:

1. **Overview** -- 2-3 sentence high-level summary of what this run accomplished.
2. **What Was Built** -- Bullet list of features/components delivered.
3. **Architecture Decisions** -- Key design choices and rationale (from design.md).
4. **Files Changed** -- Consolidated list of files created or modified across all iterations.
5. **Known Limitations** -- Issues deferred, edge cases not covered, tech debt noted.
6. **Future Work** -- Actionable next steps beyond this run's scope.

### Guidelines

- Be factual, cite specifics from the artifacts (file names, issue IDs, etc.)
- Keep the total document under 200 lines
- Do NOT invent information not present in the input artifacts
- If a section has no content, write "None identified."

---

## Task 2: Update CLAUDE.md

Read the existing `CLAUDE.md` at the project root and update it to reflect the current project state after this orchestrator run. Preserve the existing structure and conventions.

Update these aspects:
- **Project status / progress** -- mark completed features, update current state
- **Architecture notes** -- add any new components, patterns, or conventions introduced
- **Known issues / tech debt** -- sync with Known Limitations from the summary
- **Run history** -- append a one-line entry: `- {run_id}: <what was done> (iteration {{ITERATION}})`

Do NOT:
- Remove existing content that is still relevant
- Add sections that don't exist in the current CLAUDE.md structure
- Rewrite the entire file -- make targeted updates only
