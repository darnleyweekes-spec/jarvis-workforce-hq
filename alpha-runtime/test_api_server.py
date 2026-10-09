import http.client
import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from api_server import Service, make_handler


TOKEN = "test-token-with-more-than-thirty-two-characters"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service(str(Path(self.temp.name) / "alpha.sqlite3"), TOKEN)
        self.server = HTTPServer(("127.0.0.1", 0), make_handler(self.service))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, method, path, body=None, token=TOKEN, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        hdrs = dict(headers or {})
        if token is not None:
            hdrs["Authorization"] = "Bearer " + token
        if body is not None:
            hdrs["Content-Type"] = "application/json"
            body = json.dumps(body).encode()
        conn.request(method, path, body=body, headers=hdrs)
        response = conn.getresponse()
        data = json.loads(response.read())
        status = response.status
        conn.close()
        return status, data

    @staticmethod
    def valid_payload(mid="sample-1"):
        return {
            "mission_id": mid,
            "objective": "Validate metadata for incident intake",
            "owner_scope": "prime24ai",
            "project_scope": "agents",
            "access_tags": ["ops"],
            "evidence": [{
                "evidence_id": "ev-1",
                "claim": "Example incident report",
                "source": "operator",
                "retrieved_at": "2026-10-09T10:00:00Z",
                "classification": "user_input",
            }],
        }

    def test_health_auth_and_readiness(self):
        self.assertEqual(self.request("GET", "/healthz", token=None)[0], 200)
        self.assertEqual(self.request("GET", "/readyz", token=None)[0], 401)
        self.assertEqual(self.request("GET", "/readyz", token="wrong")[0], 401)
        self.assertEqual(self.request("GET", "/readyz")[0], 200)

    def test_mission_lifecycle_evaluation_and_invalidation(self):
        status, created = self.request("POST", "/v1/missions", self.valid_payload())
        self.assertEqual(status, 201)
        self.assertEqual(created["status"], "VERIFIED")
        self.assertIn("NOT fact-verified", created["summary"])
        status, fetched = self.request("GET", "/v1/missions/sample-1")
        self.assertEqual(status, 200)
        self.assertTrue(fetched["verification"]["passed"])
        status, events = self.request("GET", "/v1/missions/sample-1/events")
        self.assertEqual(status, 200)
        self.assertTrue(len(events["events"]) >= 4)
        status, evaluation = self.request(
            "GET", "/v1/missions/sample-1/evaluation"
        )
        self.assertEqual(status, 200)
        self.assertTrue(evaluation["terminal_success"])
        status, invalidated = self.request(
            "POST", "/v1/missions/sample-1/invalidate",
            {"evidence_id": "ev-1", "reason": "source retracted"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(invalidated["invalidated_evidence_ids"], ["ev-1"])
        self.assertEqual(
            self.request("GET", "/v1/missions/sample-1")[1]["status"],
            "VERIFICATION_FAILED",
        )
        self.assertFalse(
            self.request("GET", "/v1/missions/sample-1/evaluation")[1]["mission_success"]
        )
        self.assertTrue(self.service.store.verify_event_chain("sample-1"))

    def test_bad_requests_fail_closed(self):
        self.assertEqual(
            self.request("POST", "/v1/missions", self.valid_payload(), token=None)[0],
            401,
        )
        payload = self.valid_payload()
        payload["allowed_tools"] = ["email.send"]
        self.assertEqual(self.request("POST", "/v1/missions", payload)[0], 400)
        payload = self.valid_payload()
        payload["evidence"][0]["extra"] = "unsupported"
        self.assertEqual(self.request("POST", "/v1/missions", payload)[0], 400)
        payload = self.valid_payload()
        payload["project_scope"] = ""
        self.assertEqual(self.request("POST", "/v1/missions", payload)[0], 400)
        self.assertEqual(self.request("GET", "/v1/missions/nonexistent")[0], 409)
        self.assertEqual(self.request("POST", "/v1/missions", self.valid_payload())[0], 201)
        self.assertEqual(self.request("POST", "/v1/missions", self.valid_payload())[0], 500)
        self.assertEqual(self.request("POST", "/v1/missions/nope/invalidate", {})[0], 400)
        self.assertEqual(self.request("GET", "/unknown")[0], 404)

    def test_no_action_execution_endpoint(self):
        self.assertEqual(
            self.request("POST", "/v1/missions/sample-1/execute", {})[0], 404
        )

    def test_service_refuses_weak_token(self):
        with self.assertRaises(ValueError):
            Service(str(Path(self.temp.name) / "bad.sqlite3"), "short")


if __name__ == "__main__":
    unittest.main()
