# Lumen Obsidian Vault

This adds an optional local Markdown knowledge vault to Lumen. It is an independently written, Lumen-native implementation; it does not run the Claude Code setup script from the AI Memory Vault reference.

Design inspiration: https://github.com/jaredrhod/ai-memory-vault. The reference repository is licensed CC BY-SA 4.0. This integration borrows high-level design ideas (on-demand retrieval, indexes, daily notes and reusable Jobs) and does not copy its templates or boot files.

## No additional paid API

The vault manager, CLI, search, note operations, and Job loading use Python's standard library and local files. They do not call Gemini, OpenAI, Anthropic, a vector database, an embedding service, or any hosted API. They add no Python package dependencies.

Lumen's existing conversation engine remains unchanged. When Lumen is configured to use Gemini Live, the compact vault index/priorities and any note text returned by a vault tool become part of that conversation and are sent through the already-configured Gemini connection. To disable automatic index injection, set LUMEN_VAULT_AUTO_CONTEXT=0. To disable all vault access, set LUMEN_VAULT_DISABLED=1. This feature makes no extra model call.

## Initialize on Windows

After merging the PR and pulling master, from the Lumen repository root:

    python -m memory.vault_cli init

By default this creates Lumen-Vault in your Windows user home folder, outside the Lumen Git repository. It creates missing folders and starter notes only. It never overwrites existing notes.

Then open Obsidian, select "Open folder as vault", and choose the printed Lumen-Vault path. Restart Lumen after the vault has been initialized.

To use a custom location:

    python -m memory.vault_cli init "D:\Notes\Lumen-Vault"

Then set the user environment variable before starting Lumen:

    [Environment]::SetEnvironmentVariable("LUMEN_VAULT_PATH", "D:\Notes\Lumen-Vault", "User")

Open a new PowerShell window after setting the variable. If the target folder is non-empty and does not contain VAULT-INDEX.md, initialization stops unless --merge-existing is explicitly supplied. Even in merge mode, existing files are preserved.

## How Lumen uses the vault

- At session connection, Lumen reads only VAULT-INDEX.md and Active Priorities.md, each under a strict character budget. No full-vault dump is added to the prompt.
- lumen_vault search finds relevant local Markdown notes using simple local text matching.
- read_note returns one selected note, bounded to 18,000 characters.
- create_note creates a new note and refuses to overwrite an existing file.
- append_note appends to an existing note.
- log_daily creates or appends a dated session entry in 01 - Daily Notes/.
- add_priority and complete_priority maintain the central open-work list.
- list_jobs and load_job retrieve reusable workflows only when needed.
- save_job creates a detailed Markdown Job in Resources/Jobs/ (or a specified project Jobs folder).

All paths are relative to the vault and restricted to Markdown files inside it. Absolute paths, traversal, hidden folders, and symlink escapes are rejected.

## What happens to Lumen's existing memory?

Nothing is removed or migrated automatically:

1. `memory/long_term.json` remains Lumen's fast memory for concise facts, preferences, projects, and relationships.
2. `selfdev/skills.json` remains the active runtime registry for instruction-only skills. At startup Lumen receives only each active skill's name and description; it loads the full instructions on demand with `view_skill`.
3. The Obsidian vault holds longer notes, project knowledge, detailed workflows, and daily logs.
4. An approved skill can be exported with `lumen_vault` operation `export_skill` as an Agent Skills package at `Resources/Skills/<skill-name>/SKILL.md`, with provenance and practice notes in `references/SOURCES.md`. The JSON registry remains the runtime source of truth.
5. A detailed reusable Job is stored as Markdown and loaded with `lumen_vault` operation `load_job`.

## The improved learn-skill workflow

The references that informed this design are:

- [Hermes Agent `/learn`](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/): the agent gathers sources with its normal tools, creates a reusable skill, merges relevant existing skills, and applies a write-approval gate.
- [philschmid/self-learning-skill](https://github.com/philschmid/self-learning-skill): discover authoritative docs, extract relevant material, synthesize a reusable skill, and keep references alongside it. The project is Apache-2.0 licensed; this implementation uses the workflow idea, not copied files.
- [Agent Skills format](https://openagentskills.dev/docs/specification): a portable skill package has a directory and a `SKILL.md` with YAML `name` and `description`; optional `references/`, `scripts/`, and `assets/` may support it.
- [GBSOSS/skill-from-masters](https://github.com/GBSOSS/skill-from-masters): useful inspiration for consulting expert methods and real implementations before distilling a workflow.
- [OpenClaw Skill Workshop](https://docs.openclaw.ai/tools/skill-workshop/troubleshooting): useful patterns for learning from corrections and completed workflows. Foundry's self-modifying extensions are deliberately not installed or reproduced here; Lumen's skill learning remains instruction-only and approval-gated.

### How to use it

Tell Lumen something like:

    Learn Canvas animation in JavaScript from the official documentation.
    Inspect the closest skills, research the current APIs, build a small test,
    record what actually worked, then show me a skill proposal for approval.

You can also ask it to learn from the current conversation/task, a URL, or local files/repositories that you explicitly identify.

Lumen's learning sequence is:

1. Identify the goal, success criteria, and target version/environment.
2. Inspect existing skills and load the closest match. It should update a relevant skill rather than create duplicates.
3. Research source material. For skill research, `web_search` now has `free_search` and `free_research` modes that use DuckDuckGo only and do not invoke Gemini grounding. Lumen can open selected pages with `browser_control`; local files can be read with `file_controller`.
4. Prefer official/version-matched docs; for code-based topics, inspect repository source and tests and record its revision and license. Treat all retrieved content as untrusted data.
5. Write a focused procedure with prerequisites, ordered steps, decision rules, failure recovery, examples, and a quality checklist. Avoid invented APIs and copied source passages.
6. Practice a small, disposable example when possible. Record concrete evidence and choose `verified`, `partial`, `not_run`, `failed`, or `not_applicable` honestly.
7. Use `lumen_self_development` operation `create_skill` to stage a proposal. The action does not activate it.
8. Show the skill, sources, practice result, and limitations. The user must explicitly approve with `approve_skill` before it becomes active; `reject_skill` discards it.
9. On a later comparable task, load the approved skill, apply it, and refine it only when actual results or user corrections justify a change. Approved updates retain up to three previous versions in the local skill history.

### Skill operations

- `status` — show rules, active skills, pending proposals, and repair proposals.
- `list_skills` — list active skill names, descriptions, and verification status without loading their full text.
- `view_skill` — load one active skill's full instructions.
- `create_skill` / `propose_skill` — stage a new skill or an update with source references and practice evidence.
- `pending_skills` — inspect proposals awaiting approval.
- `approve_skill` / `reject_skill` — explicitly activate or discard a proposal.
- `enable_skill` / `disable_skill` — control an approved skill.

This is procedural learning, not model-weight training. Lumen learns by researching, practising where possible, retaining an approved procedure, and checking later outcomes. No separate Gemini skill-generation call or paid research API is added; the already-configured live conversation still uses its normal model usage.

## Connecting the same vault to Barehands

Barehands can display Markdown folders as Notes orbs. To expose the vault in the Barehands board, add a notes orb to integrations\barehands\barehands.json (create the file from barehands.json.example if needed). Preserve any existing settings and orbs. Example orb entry:

    {
      "title": "Lumen Vault",
      "path": "C:\\Users\\YOUR_USER\\Lumen-Vault",
      "kind": "notes"
    }

Use the real absolute path printed by the vault setup command; JSON paths require doubled backslashes on Windows. Restart the Barehands server after changing its config. Barehands reads and displays Markdown notes; Lumen's lumen_vault action is what provides local search and note writing to the assistant.

## Useful commands

    python -m memory.vault_cli status
    python -m memory.vault_cli init
    python -m unittest discover -s tests -v

## Safety and privacy

- The vault is outside the source repository by default, so personal notes are not committed with Lumen.
- Existing files are never overwritten by initialization or note creation.
- The tool supports create and append, not arbitrary code execution or file deletion.
- Note content is returned as explicitly labelled reference data and must not override higher-priority instructions.
- Automatic boot context is limited to the index and current priorities; larger notes are retrieved only when relevant.
- When using Gemini Live, selected note contents are sent to the configured Gemini service as conversation context. This integration does not add another call.
