r"""Initialize or inspect Lumen's local Obsidian vault.

Examples:
    python -m memory.vault_cli init
    python -m memory.vault_cli init "D:\Notes\Lumen-Vault" --merge-existing
    python -m memory.vault_cli status
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import vault_manager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Lumen's local Markdown vault.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Create the starter vault without overwriting notes.")
    init_parser.add_argument("path", nargs="?", help="Optional vault path; defaults to ~/Lumen-Vault.")
    init_parser.add_argument(
        "--merge-existing", action="store_true",
        help="Allow adding missing starter files to a non-empty folder that has no VAULT-INDEX.md.",
    )
    sub.add_parser("status", help="Show the configured vault path and initialization status.")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = vault_manager.initialize_vault(args.path, merge_existing=args.merge_existing)
        else:
            result = vault_manager.vault_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("success") and args.command == "init":
            root = Path(result["path"])
            print("\nNext:")
            print("  1. Open Obsidian.")
            print(f"  2. Choose 'Open folder as vault' and select: {root}")
            print("  3. Restart Lumen so it loads VAULT-INDEX.md and Active Priorities.md.")
            if args.path:
                print("\nSet this user environment variable before launching Lumen:")
                print(f'  LUMEN_VAULT_PATH={root}')
        return 0 if result.get("success") else 1
    except Exception as exc:
        print(f"Vault setup failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
