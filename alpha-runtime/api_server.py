"""Single-tenant, read-only-action ALPHA HTTP service (stdlib only).

No arbitrary Python, remote tools, approval execution, or external side effects
are exposed. Put behind an authenticated TLS reverse proxy for remote access.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from alpha_runtime import (
    AlphaRuntime, ClaimEvidenceContract, ContextPermissionDenied, Evidence,
    MissionError, MissionRequest, SpecialistResult, SQLiteMissionStore,
    Verification, VerificationFailed,
)
from evaluation_harness import AlphaEvaluationHarness

MAX_BODY = 65536
MISSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
SCOPE = re.compile(r"^[a-zA-Z0-9_.:-]{1,80}$")
CRITERION = "evidence metadata validated"


class EvidenceMetadataSpecialist:
    """Checks submitted evidence *metadata*, not the truth of its claims."""

    def run(self, task):
        if not task.evidence:
            return SpecialistResult("No evidence supplied.", errors=("missing_evidence",))
        for item in task.evidence:
            if (
                not item.source or not item.retrieved_at or not item.claim
                or item.validity_status != "active"
            ):
                return SpecialistResult(
                    "Evidence metadata incomplete.", errors=("invalid_metadata",)
                )
        return SpecialistResult(
            "Evidence metadata checked; underlying claims are NOT fact-verified.",
            completed_criteria=(CRITERION,),
            claim_evidence=(
                ClaimEvidenceContract(
                    criterion=CRITERION,
                    status="verified",
                    evidence_ids=tuple(item.evidence_id for item in task.evidence),
                    verification_method="observation:metadata_fields_present",
                ),
            ),
        )


class EvidenceMetadataVerifier:
    """Independent, narrow verifier that rejects arbitrary mission criteria."""

    def verify(self, task, result):
        valid = (
            task.success_criteria == (CRITERION,)
            and bool(task.evidence)
            and result.completed_criteria == (CRITERION,)
            and not result.errors
            and all(e.validity_status == "active" for e in task.evidence)
            and len(result.claim_evidence) == 1
            and set(result.claim_evidence[0].evidence_ids)
            == {e.evidence_id for e in task.evidence}
            and result.claim_evidence[0].status == "verified"
            and result.claim_evidence[0].verification_method
            == "observation:metadata_fields_present"
            and result.mission_state is not None
            and CRITERION in result.mission_state.completed_requirements
        )
        return Verification(
            bool(valid),
            ({"name": "metadata_only_contract", "passed": bool(valid)},),
            "Metadata verified, not factual accuracy." if valid
            else "Evidence metadata verification failed.",
        )


class Service:
    def __init__(self, db_path: str, token: str):
        if len(token) < 32:
            raise ValueError("ALPHA_API_TOKEN must be at least 32 characters")
        self._token = token.encode("utf-8")
        self.store = SQLiteMissionStore(db_path)
        self.runtime = AlphaRuntime(
            self.store, {"evidence-metadata": EvidenceMetadataSpecialist()},
            verifier=EvidenceMetadataVerifier(),
        )
        self.evals = AlphaEvaluationHarness(self.store)

    def authenticate(self, authorization: str) -> bool:
        if not authorization.startswith("Bearer "):
            return False
        supplied = authorization[7:].encode("utf-8")
        return hmac.compare_digest(supplied, self._token)

    def create_mission(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) - {
            "mission_id", "objective", "owner_scope", "project_scope",
            "access_tags", "evidence",
        }:
            raise ValueError("unknown or invalid mission fields")
        objective = payload.get("objective")
        owner = payload.get("owner_scope")
        project = payload.get("project_scope")
        if not isinstance(objective, str) or not 1 <= len(objective.strip()) <= 1000:
            raise ValueError("objective must be a nonempty string <=1000 characters")
        if not all(isinstance(x, str) and SCOPE.fullmatch(x) for x in (owner, project)):
            raise ValueError("owner_scope and project_scope are required")
        tags = payload.get("access_tags", [])
        if (
            not isinstance(tags, list) or len(tags) > 20
            or any(not isinstance(t, str) or not SCOPE.fullmatch(t) for t in tags)
        ):
            raise ValueError("invalid access_tags")
        mid = payload.get("mission_id")
        if mid is not None and (
            not isinstance(mid, str) or not MISSION_ID.fullmatch(mid)
        ):
            raise ValueError("invalid mission_id")
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, list) or not 1 <= len(raw_evidence) <= 40:
            raise ValueError("1-40 evidence records required")
        items = []
        for item in raw_evidence:
            if not isinstance(item, dict) or set(item) != {
                "evidence_id", "claim", "source", "retrieved_at", "classification"
            }:
                raise ValueError("invalid evidence record fields")
            eid = item["evidence_id"]
            if not isinstance(eid, str) or not MISSION_ID.fullmatch(eid):
                raise ValueError("invalid evidence_id")
            if not all(
                isinstance(item[k], str) and 1 <= len(item[k].strip()) <= 4000
                for k in ("claim", "source", "retrieved_at")
            ):
                raise ValueError("invalid evidence text")
            if item["classification"] not in {
                "fact", "inference", "hypothesis", "user_input"
            }:
                raise ValueError("invalid classification")
            items.append(Evidence(
                **item, owner_scope=owner, project_scope=project,
                access_tags=tuple(tags),
            ))
        if len({e.evidence_id for e in items}) != len(items):
            raise ValueError("duplicate evidence_id")
        request_data = {
            "objective": objective,
            "success_criteria": [CRITERION],
            "owner_scope": owner,
            "project_scope": project,
            "access_tags": tags,
        }
        if mid is not None:
            request_data["mission_id"] = mid
        request = MissionRequest(**request_data)
        return self.runtime.submit(request, "evidence-metadata", items)

    def invalidate(self, mission_id: str, payload: dict) -> dict:
        if (
            not isinstance(payload, dict)
            or set(payload) != {"evidence_id", "reason"}
            or not isinstance(payload["evidence_id"], str)
            or not MISSION_ID.fullmatch(payload["evidence_id"])
            or not isinstance(payload["reason"], str)
            or not 1 <= len(payload["reason"].strip()) <= 500
        ):
            raise ValueError("invalid invalidation request")
        ids = self.store.invalidate_evidence(
            mission_id, payload["evidence_id"], payload["reason"]
        )
        return {"mission_id": mission_id, "invalidated_evidence_ids": ids}


def make_handler(service: Service):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ALPHA/1.0"
        sys_version = ""

        def log_message(self, format, *args):
            # Do not log raw request paths, credentials, evidence, or payloads.
            pass

        def respond(self, status, data):
            body = json.dumps(data, sort_keys=True, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorize(self):
            if not service.authenticate(self.headers.get("Authorization", "")):
                self.respond(401, {"error": "unauthorized"})
                return False
            return True

        def route(self):
            path = urlsplit(self.path).path
            if path == "/healthz" and self.command == "GET":
                return self.respond(200, {"status": "ok"})
            if not self.authorize():
                return
            if path == "/readyz" and self.command == "GET":
                try:
                    with service.store._connect() as db:
                        db.execute("SELECT 1").fetchone()
                    return self.respond(200, {"status": "ready"})
                except Exception:
                    return self.respond(503, {"error": "not_ready"})
            if self.command == "POST":
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    return self.respond(415, {"error": "json_required"})
                length = self.headers.get("Content-Length")
                if length is None or not length.isdecimal():
                    return self.respond(411, {"error": "content_length_required"})
                size = int(length)
                if size > MAX_BODY:
                    return self.respond(413, {"error": "request_too_large"})
                if size == 0:
                    return self.respond(400, {"error": "empty_request"})
                try:
                    payload = json.loads(self.rfile.read(size))
                except (ValueError, UnicodeDecodeError):
                    return self.respond(400, {"error": "invalid_json"})
                if path == "/v1/missions":
                    result = service.create_mission(payload)
                    return self.respond(201, {
                        "mission_id": result["request"]["mission_id"],
                        "status": result["status"],
                        "summary": result["result"]["summary"],
                    })
                match = re.fullmatch(
                    r"/v1/missions/([A-Za-z0-9_-]{1,80})/invalidate", path
                )
                if match:
                    return self.respond(200, service.invalidate(match.group(1), payload))
            if self.command == "GET":
                match = re.fullmatch(
                    r"/v1/missions/([A-Za-z0-9_-]{1,80})(?:/(events|evaluation))?",
                    path,
                )
                if match:
                    mid, suffix = match.groups()
                    if suffix == "events":
                        return self.respond(200, {"events": service.store.events(mid)})
                    if suffix == "evaluation":
                        return self.respond(200, asdict(service.evals.evaluate(mid)))
                    result = service.store.get(mid)
                    return self.respond(200, {
                        "mission_id": mid,
                        "status": result["status"],
                        "result": result["result"],
                        "verification": result["verification"],
                        "mission_state": result["mission_state"],
                    })
            return self.respond(404, {"error": "not_found"})

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def dispatch(self):
            try:
                self.route()
            except (ValueError, ContextPermissionDenied, VerificationFailed) as exc:
                self.respond(400, {"error": type(exc).__name__})
            except (MissionError, sqlite3.IntegrityError):
                self.respond(409, {"error": "mission_conflict_or_missing"})
            except Exception:
                self.respond(500, {"error": "internal_error"})

    return Handler


def main():
    token = os.environ.get("ALPHA_API_TOKEN", "")
    db = os.environ.get("ALPHA_DB_PATH", "/data/alpha.sqlite3")
    host = os.environ.get("ALPHA_BIND", "127.0.0.1")
    port = int(os.environ.get("ALPHA_PORT", "8080"))
    if host not in {"127.0.0.1", "0.0.0.0", "::1"}:
        raise ValueError("ALPHA_BIND must be a valid deployment binding")
    if not 1 <= port <= 65535:
        raise ValueError("invalid ALPHA_PORT")
    service = Service(db, token)
    server = HTTPServer((host, port), make_handler(service))
    server.timeout = 10
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
