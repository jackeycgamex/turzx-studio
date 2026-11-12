"""Offline tests for ChatGPT response semantics and credential boundaries."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chatgpt_account import ChatGPTAccountReader, ChatGPTSourceError, NoRedirect, normalize_billing, normalize_feature_limits, normalize_voice, normalize_pricing


class Response(io.BytesIO):
    pass


class FakeOpener:
    def __init__(self, payload=None, error=None):
        self.payload=payload
        self.error=error
        self.requests=[]

    def open(self, request, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        return Response(json.dumps(self.payload).encode())


class NormalizationTests(unittest.TestCase):
    def test_counts_are_not_context_sizes_or_percentages(self):
        raw={"limits_progress":[{"feature_name":"deep_research","remaining":0,"reset_after":"2026-12-12T10:00:00Z"},
                                {"feature_name":"image_gen","remaining":1000,"reset_after":"2026-11-14T10:00:00Z"}],
             "model_limits":[],"max_tokens":128000}
        result=normalize_feature_limits(raw)
        self.assertEqual([i["remaining"] for i in result["items"]],[0,1000])
        self.assertEqual(result["items"][0]["unit"],"次")
        self.assertNotIn("total",result["items"][0])
        self.assertFalse(result["model_counters_provided"])

    def test_unknown_counts_dates_and_features_are_preserved_safely(self):
        for value in (None,True,"100",float("inf"),-1):
            result=normalize_feature_limits({"limits_progress":[{"feature_name":"new_feature","remaining":value,"reset_after":"2026-11-14"}]})
            self.assertIsNone(result["items"][0]["remaining"])
            self.assertIsNone(result["items"][0]["resets_at"])
            self.assertEqual(result["items"][0]["name"],"new_feature")

    def test_renewal_is_not_entitlement_expiry_or_fabricated_charge(self):
        result=normalize_billing({"is_active":True,"will_renew":False,"active_until":"2026-12-11T08:38:09Z",
                                  "entitlement":{"renews_at":"2026-12-11T08:38:09Z","expires_at":"2026-12-12T09:38:09Z",
                                                 "billing_currency":"USD"},"id":"private-sub-id"})
        self.assertFalse(result["will_renew"])
        self.assertNotEqual(result["renews_at"],result["expires_at"])
        self.assertIsNone(result["renewal_amount"])
        self.assertNotIn("private-sub-id",str(result))

    def test_absent_billing_flags_are_unknown(self):
        result=normalize_billing({})
        self.assertIsNone(result["active"])
        self.assertIsNone(result["will_renew"])
        self.assertIsNone(result["renews_at"])

    def test_model_restrictions_are_not_remaining_counts(self):
        result=normalize_feature_limits({"model_limits":[{"model_slug":"model-a","resets_after":"2027-01-01T00:00:00Z","using_default_model_slug":"model-b"}],
                                         "blocked_features":[{"name":"image_gen","resets_after":"2027-01-01T00:00:00Z"}]})
        self.assertEqual(result["items"],[])
        self.assertFalse(result["model_counters_provided"])
        self.assertTrue(result["model_status_provided"])
        self.assertEqual(result["model_restrictions"][0]["fallback_model"],"model-b")
        self.assertGreater(result["model_restrictions"][0]["resets_at"],0)
        self.assertEqual(result["blocked_features"],["image_gen"])

    def test_voice_available_is_not_unlimited_or_a_numeric_counter(self):
        for metadata, expected in ((None,True),({},False),("unexpected",None)):
            result=normalize_voice({"modes":[{"mode":"advanced","disabled_mode_metadata":metadata}],
                                    "chatreq_token":"SECRET","chatreq":{"token":"SECRET","proofofwork":{"seed":"SECRET"}}})
            self.assertIs(result["modes"][0]["available"],expected)
            self.assertIsNone(result["modes"][0]["remaining_minutes"])
            self.assertNotIn("SECRET",str(result))
        self.assertIsNone(normalize_voice({"modes":[{"mode":"advanced"}]})["modes"][0]["available"])

    def test_reference_price_does_not_convert_annual_equivalent_or_mix_currency(self):
        raw={"country_code":"US","currency_config":{"symbol_code":"USD","pro":{"month":{"amount":200}},"plus":{"year":{"amount":16.67}}}}
        result=normalize_pricing(raw)
        self.assertEqual(result["monthly_prices"],{"chatgptpro":200})
        self.assertEqual(result["kind"],"catalog_reference")
        raw["currency_config"]["symbol_code"]="SGD"
        self.assertEqual(normalize_pricing(raw)["monthly_prices"],{})


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'auth.json'
        payload=base64.urlsafe_b64encode(json.dumps({"email":"one@example.com"}).encode()).decode().rstrip('=')
        self.path.write_text(json.dumps({"tokens":{"access_token":"fake-private-token","account_id":"fake-account-id",
                                                    "id_token":"header."+payload+".signature"}}),encoding='utf-8')

    def test_quota_query_has_no_prompt_and_uses_only_official_origin(self):
        opener=FakeOpener({"limits_progress":[],"model_limits":[]})
        reader=ChatGPTAccountReader(self.path,opener)
        data=reader.read_limits('one@example.com')
        request=opener.requests[0]
        self.assertEqual(urlsplit(request.full_url).netloc,'chatgpt.com')
        self.assertEqual(request.get_method(),'POST')
        self.assertEqual(json.loads(request.data),{})
        self.assertNotIn('fake-private-token',str(data))

    def test_billing_is_a_get_for_the_signed_in_account(self):
        opener=FakeOpener({"entitlement":{},"is_active":True})
        ChatGPTAccountReader(self.path,opener).read_billing('one@example.com')
        request=opener.requests[0]
        self.assertEqual(request.get_method(),'GET')
        self.assertEqual(parse_qs(urlsplit(request.full_url).query),{'account_id':['fake-account-id']})

    def test_identity_mismatch_never_sends_a_request(self):
        opener=FakeOpener({})
        with self.assertRaises(ChatGPTSourceError) as caught:
            ChatGPTAccountReader(self.path,opener).read_limits('someone-else@example.com')
        self.assertTrue(caught.exception.clear_cache)
        self.assertEqual(opener.requests,[])

    def test_error_payload_and_token_are_never_exposed(self):
        error=urllib.error.HTTPError('https://chatgpt.com/',403,'fake-private-token',{},None)
        opener=FakeOpener(error=error)
        with self.assertRaises(ChatGPTSourceError) as caught:
            ChatGPTAccountReader(self.path,opener).read_limits('one@example.com')
        self.assertNotIn('fake-private-token',str(caught.exception))

    def test_redirects_and_unknown_response_shape_fail_closed(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://example.com/'))
        with self.assertRaises(ChatGPTSourceError):
            ChatGPTAccountReader(self.path,FakeOpener({"unexpected":"value"})).read_limits('one@example.com')

    def test_voice_reads_status_without_starting_a_call(self):
        opener=FakeOpener({"modes":[],"chatreq_token":"SECRET"})
        result=ChatGPTAccountReader(self.path,opener).read_voice('one@example.com')
        request=opener.requests[0]
        self.assertEqual(request.full_url,'https://chatgpt.com/realtime/status')
        self.assertEqual(request.get_method(),'POST')
        self.assertEqual(json.loads(request.data),{})
        self.assertNotIn('SECRET',str(result))

    def test_pricing_uses_fixed_read_only_catalog(self):
        opener=FakeOpener({"country_code":"US","currency_config":{"symbol_code":"USD"}})
        ChatGPTAccountReader(self.path,opener).read_pricing('one@example.com')
        request=opener.requests[0]
        self.assertEqual(request.get_method(),'GET')
        self.assertEqual(request.full_url,'https://chatgpt.com/backend-api/checkout_pricing_config/configs/US')
        for method in ('read_voice','read_pricing'):
            with self.assertRaises(ChatGPTSourceError):
                getattr(ChatGPTAccountReader(self.path,FakeOpener({})),method)('one@example.com')


if __name__=='__main__':
    unittest.main()
