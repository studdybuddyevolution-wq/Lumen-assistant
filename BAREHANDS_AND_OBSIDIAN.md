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

1. memory/long_term.json remains Lumen's fast memory for concise facts, preferences, projects, and relationships.
2. selfdev/skills.json remains the active registry for short instruction-only skills. These skills continue to be included in Lumen's bounded prompt context.
3. The Obsidian vault holds longer notes, project knowledge, detailed workflows, and daily logs.
4. A skill can be exported to Resources/Skills/ with lumen_vault operation export_skill. The JSON registry remains the runtime source of truth; the Markdown file is a readable copy.
5. A detailed reusable Job is stored as Markdown and loaded with lumen_vault operation load_job.

## The learn-skill system

The existing lumen_self_development tool still supports learn_rule, create_skill, disable_skill, and guarded repair proposals.

- Learned rule: a short, user-approved preference or invariant. Stored in Lumen's local self-development data.
- Instruction skill: a compact reusable procedure saved in skills.json, automatically available to Lumen when relevant. It contains instructions only; it cannot execute Python or shell code.
- Vault Job: a longer, task-specific playbook with a procedure, quality bar, linked references, and lessons. Lumen loads only the requested Job when doing that kind of work.
- Code repair proposal: separate from both; it remains a reviewed proposal with explicit local apply/rollback.

Creating an instruction skill no longer makes a separate Gemini generation call. Lumen drafts the instructions in the current conversation, then passes the name, description, and instructions to the local create_skill handler for storage. To save the same skill as a Markdown note, call lumen_vault with export_skill and its ID or slug. This does not execute the skill or change its permissions.

Skills and Jobs are not learned from untrusted webpages or files automatically. Only persist a reusable lesson when the user asks Lumen to learn it or approves the proposed lesson.

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
