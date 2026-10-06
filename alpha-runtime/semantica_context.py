"""Read-only Semantica context projection of one ALPHA mission.

SQLite remains authoritative. Build a new, mission-scoped graph per request.
No model calls, external writes, approval changes, or automatic execution.
"""
from __future__ import annotations

import hashlib
import json

from alpha_runtime import SQLiteMissionStore, MissionError


class SemanticaContext:
    def __init__(self, store: SQLiteMissionStore):
        self.store = store

    def build_graph(self, mission_id: str):
        if not self.store.verify_event_chain(mission_id):
            raise MissionError("Cannot project a mission with an invalid event chain")
        mission = self.store.get(mission_id)
        from semantica.context import ContextGraph
        graph = ContextGraph()
        root = "mission:" + mission_id
        graph.add_node(root, "mission", mission["request"]["objective"],
                       status=mission["status"], mission_id=mission_id)
        state = mission["mission_state"] or {}
        graph.add_node(root + ":state", "mission_state", json.dumps(state, sort_keys=True))
        graph.add_edge(root, root + ":state", "has_state")
        evidence_ids = {}
        for item in mission["evidence"]:
            key = hashlib.sha256(item["evidence_id"].encode()).hexdigest()
            node_id = root + ":evidence:" + key
            evidence_ids[item["evidence_id"]] = node_id
            graph.add_node(node_id, "evidence", item["claim"],
                           source=item["source"], classification=item["classification"],
                           retrieved_at=item["retrieved_at"],
                           expires_at=item.get("expires_at"),
                           freshness_seconds=item.get("freshness_seconds"))
            graph.add_edge(root, node_id, "has_evidence")
        result = mission["result"] or {}
        for index, contract in enumerate(result.get("claim_evidence", [])):
            node_id = root + ":claim:" + str(index)
            graph.add_node(node_id, "claim", contract["criterion"],
                           status=contract["status"],
                           verification_method=contract["verification_method"])
            graph.add_edge(root, node_id, "has_claim")
            for evidence_id in contract["evidence_ids"]:
                if evidence_id not in evidence_ids:
                    raise MissionError("Claim references unknown evidence")
                graph.add_edge(node_id, evidence_ids[evidence_id], "references_evidence")
        previous = root
        for event in self.store.events(mission_id):
            node_id = root + ":event:" + str(event["seq"])
            graph.add_node(node_id, "event", event["event_type"],
                           payload=event["payload"], ledger_hash=event["event_hash"])
            graph.add_edge(previous, node_id, "next_event")
            previous = node_id
        if mission["verification"] is not None:
            node_id = root + ":verification"
            graph.add_node(node_id, "verification",
                           json.dumps(mission["verification"], sort_keys=True))
            graph.add_edge(root, node_id, "has_verification")
        return graph
