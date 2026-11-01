"""Approval CLI: list / approve / apply proposals.

    python -m pmf_agent.approval_cli list   --store workspace
    python -m pmf_agent.approval_cli approve prop-abc123 --approver U123 --store workspace
    python -m pmf_agent.approval_cli apply prop-abc123 --store workspace
"""

from __future__ import annotations

import argparse
import sys

from .approval import ProposalStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pmf_agent.approval_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--store", default="workspace")
    p_list.add_argument("--status", choices=["pending", "approved", "applied"])

    p_approve = sub.add_parser("approve")
    p_approve.add_argument("proposal_id")
    p_approve.add_argument("--approver", required=True)
    p_approve.add_argument("--store", default="workspace")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("proposal_id")
    p_apply.add_argument("--store", default="workspace")

    args = parser.parse_args(argv)
    store = ProposalStore(args.store, allowlist_path=f"{args.store}/approvers.txt")

    try:
        if args.cmd == "list":
            proposals = store.list(status=args.status)
            if not proposals:
                print("no proposals")
            for p in proposals:
                print(f"{p['proposal_id']}  {p['status']:9s}  {p['platform']:11s}  {p['change_type']}: {p['details']}")
            return 0
        if args.cmd == "approve":
            p = store.approve(args.proposal_id, approver_id=args.approver)
            print(f"{p['proposal_id']} approved by {p['approved_by']}")
            return 0
        if args.cmd == "apply":
            p = store.apply(args.proposal_id)
            verified = "verified" if p.get("verified") else "NOT VERIFIED"
            print(f"{p['proposal_id']} applied ({verified})")
            return 0
    except (PermissionError, RuntimeError, KeyError, ValueError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
