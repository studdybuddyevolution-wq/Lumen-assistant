"""Local, interactive controls for reviewing, applying and rolling back repairs."""
from __future__ import annotations

import argparse

from .repair import apply_proposal, get_proposal, list_proposals, rollback_proposal


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumen guarded self-development tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List repair proposals")
    show = sub.add_parser("show", help="Show a proposal diff")
    show.add_argument("proposal_id")
    apply = sub.add_parser("apply", help="Review and apply a proposal with confirmation")
    apply.add_argument("proposal_id")
    rollback = sub.add_parser("rollback", help="Restore the backup for an applied proposal")
    rollback.add_argument("proposal_id")
    args = parser.parse_args()

    if args.command == "list":
        items = list_proposals()
        if not items:
            print("No repair proposals found.")
        for item in items:
            print(f"{item.get('id')}  {item.get('status')}  {item.get('target')}  {item.get('summary', '')}")
        return 0

    if args.command == "show":
        item = get_proposal(args.proposal_id)
        print(item.get("diff", "(no diff)"))
        return 0

    if args.command == "apply":
        item = get_proposal(args.proposal_id)
        print(item.get("diff", "(no diff)"))
        print("\nThis will replace the target file. A backup will be created first.")
        answer = input(f"Type APPLY {args.proposal_id} to continue: ").strip()
        if answer != f"APPLY {args.proposal_id}":
            print("Cancelled; no files were changed.")
            return 1
        print(apply_proposal(args.proposal_id)["message"])
        return 0

    if args.command == "rollback":
        answer = input(f"Type ROLLBACK {args.proposal_id} to restore its backup: ").strip()
        if answer != f"ROLLBACK {args.proposal_id}":
            print("Cancelled; no files were changed.")
            return 1
        print(rollback_proposal(args.proposal_id)["message"])
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
