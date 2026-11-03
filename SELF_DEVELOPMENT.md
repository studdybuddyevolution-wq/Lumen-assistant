# Lumen guarded self-development

This integration adds user-approved learned rules, instruction-only skills, and a reviewed repair-proposal workflow. It does not replace the Gemini Live engine, provider registry, or API-key configuration.

## What it adds

- `lumen_self_development` is discovered by Lumen's existing `actions/*.py` loader.
- `learn_rule` saves a user preference; `disable_rule` turns it off.
- `create_skill` asks the existing `core.gemini` ladder to draft an instruction-only workflow. It is stored locally and included in the next system-prompt build. Skills do not install or execute scripts.
- `propose_repair` asks Gemini for a replacement Python file, runs syntax/AST checks, and saves a unified diff. It never edits the source file during a conversation tool call.
- Repairs are restricted to existing `.py` files under `actions/` and `plugins/`. `main.py`, `ui.py`, `core/gemini.py`, provider/configuration code, the self-development action, and the existing project/code agents are protected.
- Repair proposals record the original file hash. Applying a stale proposal is refused. Applying a proposal creates a user-data backup; rollback refuses to overwrite later manual edits.

## Review and apply a code repair

From the Lumen repository root, run:

```powershell
python -m selfdev.cli list
python -m selfdev.cli show <proposal-id>
python -m selfdev.cli apply <proposal-id>
```

The apply command prints the diff and requires typing the exact `APPLY <proposal-id>` confirmation. To restore the backup:

```powershell
python -m selfdev.cli rollback <proposal-id>
```

The CLI compiles the candidate before writing it, but this is not a substitute for running the project's test suite and manually reviewing the diff. Do not apply proposals you do not understand.

## State and configuration

Set `LUMEN_SELFDEV_DISABLED=1` to disable learning, prompt injection, and applying new repairs as an emergency kill switch. Rollback remains available so a damaged file can still be restored.

Runtime state is stored under `%LOCALAPPDATA%\Lumen\selfdev` on Windows or `$XDG_DATA_HOME/Lumen/selfdev` (default `~/.local/share/Lumen/selfdev`) on Linux/macOS. No code in this integration reads, rewrites, or migrates `config/api_keys.json`. Repair proposals and backups are not committed to Git.

## Security boundary

AST parsing checks syntax only; it is not a secure sandbox for executing arbitrary code. This integration therefore does not execute generated code, install generated dependencies, or auto-apply patches. Gemini calls use Lumen's existing `core.gemini` wrapper and its current configured key/fallback behavior.
