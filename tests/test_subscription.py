"""Account-data semantics, privacy and stale-cache regression coverage."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from subscription import CodexAccountClient, SourceError, SubscriptionMonitor, normalize_limits
from chatgpt_account import ChatGPTSourceError


def account(email="one@example.com", plan="pro"):
    return {"account": {"type": "chatgpt", "email": email, "planType": plan}}


def limits(used=21):
    return {"rateLimitsByLimitId": {"codex": {"primary": {
        "usedPercent": used, "windowDurationMins": 10080, "resetsAt": 2000000000,
    }, "credits": {"balance": "12.5", "hasCredits": True, "unlimited": False}}},
        "rateLimitResetCredits": {"availableCount": 2}}


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, params=None):
        self.calls.append((method, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)

    def close(self):
        pass


class FakeWebClient:
    def __init__(self):
        self.limit_calls = 0
        self.billing_calls = 0
        self.voice_calls = 0
        self.pricing_calls = 0
        self.voice_failure = None
        self.failure = None
        self.identity = "account-a"

    def bind_account(self, email):
        return self.identity

    def read_limits(self, email):
        self.limit_calls += 1
        if self.failure:
            raise self.failure
        return {"items": [{"id":"deep_research", "remaining":12}], "blocked_features":[]}

    def read_billing(self, email):
        self.billing_calls += 1
        if self.failure:
            raise self.failure
        return {"active":True, "will_renew":True, "renews_at":2000000000}

    def read_voice(self, email):
        self.voice_calls += 1
        if self.failure or self.voice_failure:
            raise self.failure or self.voice_failure
        return {"modes":[{"id":"advanced","name":"高级语音","available":True,"remaining_minutes":None}]}

    def read_pricing(self, email):
        self.pricing_calls += 1
        if self.failure:
            raise self.failure
        return {"monthly_prices":{"chatgptpro":200},"currency":"USD","kind":"catalog_reference"}


class NormalizeTests(unittest.TestCase):
    def test_multi_bucket_replaces_legacy_and_preserves_windows(self):
        data = limits()
        data["rateLimits"] = {"primary": {"usedPercent": 99}}
        data["rateLimitsByLimitId"]["other"] = {"secondary": {"usedPercent": 100}}
        result = normalize_limits(data)
        self.assertEqual(len(result["buckets"]), 2)
        self.assertEqual(result["buckets"][0]["windows"][0]["remaining_percent"], 79)
        self.assertEqual(result["buckets"][1]["windows"][0]["remaining_percent"], 0)

    def test_missing_values_are_not_zero_or_unlimited(self):
        data = {"rateLimits": {"primary": {}, "credits": {}}}
        result = normalize_limits(data)
        bucket = result["buckets"][0]
        self.assertIsNone(bucket["windows"][0]["remaining_percent"])
        self.assertIsNone(bucket["windows"][0]["resets_at"])
        self.assertIsNone(bucket["credits"]["balance"])
        self.assertIsNone(bucket["credits"]["has_credits"])
        self.assertFalse(bucket["credits"]["unlimited"])
        self.assertIsNone(result["reset_count"])

    def test_empty_authoritative_map_does_not_resurrect_legacy(self):
        self.assertEqual(normalize_limits({"rateLimitsByLimitId": {}, "rateLimits": {"primary": {}}})["buckets"], [])

    def test_zero_used_is_one_hundred_remaining(self):
        self.assertEqual(normalize_limits(limits(0))["buckets"][0]["windows"][0]["remaining_percent"], 100)

    def test_invalid_numeric_values_do_not_reach_ui(self):
        for invalid in (True, float("nan"), float("inf"), "12", None):
            with self.subTest(invalid=invalid):
                result = normalize_limits(limits(invalid))
                self.assertIsNone(result["buckets"][0]["windows"][0]["remaining_percent"])
        self.assertEqual(normalize_limits(limits(110))["buckets"][0]["windows"][0]["remaining_percent"], 0)
        self.assertEqual(normalize_limits(limits(-1))["buckets"][0]["windows"][0]["remaining_percent"], 100)

    def test_credits_keep_unit_and_explicit_unlimited(self):
        for balance in ("nan", "Infinity", "-1", None):
            data = limits()
            data["rateLimitsByLimitId"]["codex"]["credits"]["balance"] = balance
            self.assertIsNone(normalize_limits(data)["buckets"][0]["credits"]["balance"])
        data = limits()
        data["rateLimitsByLimitId"]["codex"]["credits"]["unlimited"] = True
        self.assertTrue(normalize_limits(data)["buckets"][0]["credits"]["unlimited"])


class MonitorTests(unittest.TestCase):
    def make_monitor(self, responses):
        self.now = 1000
        client = FakeClient(responses)
        monitor = SubscriptionMonitor(client=client, clock=lambda:self.now, autostart=False, web_client=FakeWebClient())
        self.addCleanup(monitor.close)
        return monitor, client

    def test_live_snapshot_is_masked_and_read_only(self):
        monitor, client = self.make_monitor([account(), limits()])
        monitor._poll()
        snap = monitor.snapshot()
        self.assertEqual(snap["status"], "live")
        self.assertEqual(snap["account"]["email"], "o•••@example.com")
        self.assertNotIn("one@example.com", str(snap))
        self.assertEqual(client.calls, [("account/read", {"refreshToken":False}), ("account/rateLimits/read", None)])
        self.assertEqual(snap["observed_at"], 1000)
        snap["buckets"].clear()
        self.assertEqual(len(monitor.snapshot()["buckets"]), 1)

    def test_network_failure_retains_old_values_with_original_timestamp(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), SourceError("offline")])
        monitor._poll()
        self.now = 1060
        monitor._poll()
        snap = monitor.snapshot()
        self.assertEqual(snap["status"], "stale")
        self.assertEqual(snap["observed_at"], 1000)
        self.assertEqual(snap["buckets"][0]["windows"][0]["remaining_percent"], 79)

    def test_account_switch_cannot_reuse_previous_account_limits(self):
        monitor, _ = self.make_monitor([account(), limits(), account("two@example.com"), SourceError("offline")])
        monitor._poll()
        monitor._poll()
        snap = monitor.snapshot()
        self.assertEqual(snap["account"]["email"], "t•••@example.com")
        self.assertEqual(snap["buckets"], [])
        self.assertIsNone(snap["observed_at"])
        self.assertEqual(snap["status"], "error")

    def test_logout_clears_data_without_calling_limit_api(self):
        monitor, client = self.make_monitor([account(), limits(), {"account":None}])
        monitor._poll()
        monitor._poll()
        snap = monitor.snapshot()
        self.assertEqual(snap["status"], "disconnected")
        self.assertIsNone(snap["account"])
        self.assertEqual(snap["buckets"], [])
        self.assertEqual(len(client.calls), 3)

    def test_age_alone_expires_snapshot_and_recovery_clears_failure(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits(30)])
        monitor._poll()
        self.now = 1181
        self.assertEqual(monitor.snapshot()["status"], "stale")
        monitor._poll()
        self.assertEqual(monitor.snapshot()["status"], "live")
        self.assertEqual(monitor.snapshot()["buckets"][0]["windows"][0]["remaining_percent"], 70)

    def test_unexpected_errors_never_expose_raw_messages(self):
        monitor, _ = self.make_monitor([RuntimeError("SECRET_CREDENTIAL")])
        monitor._poll()
        self.assertNotIn("SECRET_CREDENTIAL", str(monitor.snapshot()))

    def test_client_rejects_reset_or_billing_mutations(self):
        client = CodexAccountClient()
        with self.assertRaises(ValueError):
            client.request("account/rateLimitResetCredit/consume")
        self.assertIsNone(client.process)

    def test_chatgpt_refreshes_even_when_codex_limits_fail(self):
        monitor, _ = self.make_monitor([account(), SourceError("offline")])
        monitor._poll()
        snap=monitor.snapshot()
        self.assertEqual(snap["status"], "error")
        self.assertEqual(snap["chatgpt_feature_limits"]["status"], "live")
        self.assertEqual(snap["billing"]["status"], "live")

    def test_source_failure_does_not_replace_true_counts_or_timestamps(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits()])
        monitor._poll()
        self.now=1061
        monitor.web_client.failure=ChatGPTSourceError("offline")
        monitor._poll()
        snap=monitor.snapshot()
        self.assertEqual(snap["status"], "live")
        self.assertEqual(snap["chatgpt_feature_limits"]["status"], "stale")
        self.assertEqual(snap["chatgpt_feature_limits"]["observed_at"], 1000)
        self.assertEqual(snap["chatgpt_feature_limits"]["items"][0]["remaining"], 12)

    def test_billing_cadence_and_manual_refresh(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits(), account(), limits()])
        monitor._poll()
        self.now=1061
        monitor._poll()
        self.assertEqual(monitor.web_client.limit_calls,2)
        self.assertEqual(monitor.web_client.billing_calls,1)
        self.assertEqual(monitor.web_client.voice_calls,2)
        self.assertEqual(monitor.web_client.pricing_calls,1)
        monitor.refresh()
        monitor._poll()
        self.assertEqual(monitor.web_client.billing_calls,2)
        self.assertEqual(monitor.web_client.pricing_calls,2)

    def test_account_mismatch_clears_web_cache(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits()])
        monitor._poll()
        monitor.web_client.failure=ChatGPTSourceError("mismatch", clear_cache=True)
        monitor.refresh()
        monitor._poll()
        for field in ("chatgpt_feature_limits","billing","chatgpt_voice","plan_pricing"):
            self.assertEqual(monitor.snapshot()[field]["status"], "error")
            self.assertIsNone(monitor.snapshot()[field]["observed_at"])
            self.assertNotIn("items",monitor.snapshot()[field])
            self.assertNotIn("modes",monitor.snapshot()[field])
            self.assertNotIn("monthly_prices",monitor.snapshot()[field])

    def test_voice_failure_does_not_age_other_sources(self):
        monitor, _ = self.make_monitor([account(),limits(),account(),limits()])
        monitor._poll()
        self.now=1061
        monitor.web_client.voice_failure=ChatGPTSourceError("voice offline")
        monitor._poll()
        snap=monitor.snapshot()
        self.assertEqual(snap["chatgpt_voice"]["status"],"stale")
        self.assertEqual(snap["chatgpt_voice"]["observed_at"],1000)
        self.assertEqual(snap["chatgpt_feature_limits"]["status"],"live")
        self.assertEqual(snap["plan_pricing"]["status"],"live")
        self.now=4601
        self.assertEqual(monitor.snapshot()["plan_pricing"]["status"],"stale")

    def test_identity_failure_clears_cached_billing_without_force(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits()])
        monitor._poll()
        self.now=1061
        monitor.web_client.failure=ChatGPTSourceError("mismatch", clear_cache=True)
        monitor._poll()
        self.assertEqual(monitor.snapshot()["billing"]["status"], "error")
        self.assertIsNone(monitor.snapshot()["billing"]["observed_at"])
        self.assertNotIn("renews_at",monitor.snapshot()["billing"])

    def test_same_email_workspace_change_invalidates_billing_cache(self):
        monitor, _ = self.make_monitor([account(), limits(), account(), limits()])
        monitor._poll()
        self.now=1061
        monitor.web_client.identity="account-b"
        monitor._poll()
        self.assertEqual(monitor.web_client.billing_calls,2)
        self.assertEqual(monitor.snapshot()["billing"]["observed_at"],1061)


if __name__ == "__main__":
    unittest.main()
