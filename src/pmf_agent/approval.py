"""Approval workflow: pending proposals -> permission-checked approval -> apply + verify.

The PMA contract, in-process: the agent proposes, a human approves (allowlist
checked here, not by the model), code applies, and code verifies the change
landed. The apply path is deliberately absent from the agent's tool surface.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path

from .tools import PLATFORMS

MUTABLE_CHANGE_TYPES = (
    "add_keywords",
    "update_budget",
    "update_targeting",
    "update_copy",
    "pause_campaign",
)


class ProposalStore:
    def __init__(self, root: str | Path, allowlist_path: str | Path | None = None) -> None:
        self.root = Path(root)
        self.proposals_dir = self.root / "proposals"
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.proposals_dir / "_mutations.json"
        self.allowlist_path = Path(allowlist_path) if allowlist_path else None

    # -- proposal lifecycle ----------------------------------------------------

    def submit(
        self, platform: str, change_type: str, details: str, rationale: str
    ) -> dict:
        if platform not in PLATFORMS:
            raise ValueError(
                f"unknown platform {platform!r}; known: {', '.join(sorted(PLATFORMS))}"
            )
        proposal = {
            "proposal_id": f"prop-{uuid.uuid4().hex[:8]}",
            "status": "pending",
            "platform": platform,
            "change_type": change_type,
            "details": details,
            "rationale": rationale,
            "submitted_at": _now(),
            "approved_by": None,
            "approved_at": None,
        }
        self._write(proposal)
        return proposal

    def get(self, proposal_id: str) -> dict:
        return self._read(proposal_id)

    def list(self, status: str | None = None) -> list[dict]:
        out = []
        for f in sorted(self.proposals_dir.glob("prop-*.json")):
            p = self._read(f.stem)
            if status is None or p["status"] == status:
                out.append(p)
        return out

    def approve(self, proposal_id: str, approver_id: str) -> dict:
        if not self._is_approver(approver_id):
            raise PermissionError(
                f"approver {approver_id!r} is not on the allowlist; "
                "the proposal remains pending"
            )
        proposal = self._read(proposal_id)
        if proposal["status"] == "applied":
            raise RuntimeError(f"{proposal_id} already applied")
        proposal["status"] = "approved"
        proposal["approved_by"] = approver_id
        proposal["approved_at"] = _now()
        self._write(proposal)
        return proposal

    def apply(self, proposal_id: str) -> dict:
        proposal = self._read(proposal_id)
        if proposal["status"] == "pending":
            raise RuntimeError(f"{proposal_id} is pending; refusing to apply an unapproved change")
        if proposal["status"] == "applied":
            raise RuntimeError(f"{proposal_id} already applied")
        if proposal["platform"] not in PLATFORMS:
            raise ValueError(f"unknown platform {proposal['platform']!r}")

        # apply = record the mutation in the fixture ledger (stand-in for the
        # ad-platform API call), then verify by reading it back
        ledger = self._load_ledger()
        entry = {
            "proposal_id": proposal_id,
            "platform": proposal["platform"],
            "change_type": proposal["change_type"],
            "details": proposal["details"],
            "applied_at": _now(),
        }
        ledger.append(entry)
        self.ledger_path.write_text(json.dumps(ledger, indent=2))

        verified = self._verify(entry)
        proposal["status"] = "applied"
        proposal["verified"] = verified
        proposal["applied_at"] = entry["applied_at"]
        self._write(proposal)
        return proposal

    # -- internals ------------------------------------------------------------

    def _verify(self, entry: dict) -> bool:
        ledger = self._load_ledger()
        return any(
            m["proposal_id"] == entry["proposal_id"]
            and m["platform"] == entry["platform"]
            and m["change_type"] == entry["change_type"]
            for m in ledger
        )

    def _load_ledger(self) -> list[dict]:
        if self.ledger_path.exists():
            return json.loads(self.ledger_path.read_text())
        return []

    def _is_approver(self, approver_id: str) -> bool:
        env_ids = [i.strip() for i in os.environ.get("PMF_APPROVERS", "").split(",") if i.strip()]
        ids = env_ids
        if self.allowlist_path and self.allowlist_path.exists():
            ids = ids or [
                i.strip()
                for i in self.allowlist_path.read_text().splitlines()
                if i.strip()
            ]
        return bool(ids) and approver_id in ids  # empty/missing allowlist fails closed

    def _path(self, proposal_id: str) -> Path:
        return self.proposals_dir / f"{proposal_id}.json"

    def _read(self, proposal_id: str) -> dict:
        path = self._path(proposal_id)
        if not path.exists():
            raise KeyError(f"no proposal {proposal_id!r}")
        return json.loads(path.read_text())

    def _write(self, proposal: dict) -> None:
        self._path(proposal["proposal_id"]).write_text(json.dumps(proposal, indent=2))


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()
