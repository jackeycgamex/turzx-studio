"""Read ChatGPT feature counters and renewal state from the signed-in account.

The web-account endpoints are not a versioned public API. Keep requests bounded,
allowlisted and credential-safe, and treat unknown fields as unavailable.
"""
from __future__ import annotations

import base64
from datetime import datetime
import json
import hashlib
import math
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


class ChatGPTSourceError(Exception):
    def __init__(self, message, clear_cache=False):
        super().__init__(message)
        self.clear_cache = clear_cache


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def timestamp(value):
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            value = parsed.timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    value = number(value)
    return value if value is not None and 0 < value < 253402300800 else None


def text(value, limit=120):
    return value[:limit] if isinstance(value, str) and value else None


def boolean(value):
    return value if type(value) is bool else None


def normalize_billing(raw):
    entitlement = raw.get("entitlement")
    entitlement = entitlement if isinstance(entitlement, dict) else {}
    last = raw.get("last_active_subscription")
    last = last if isinstance(last, dict) else {}
    # In particular, expires_at can include a grace period. It is NOT renews_at.
    return {
        "plan_type": text(raw.get("plan_type")),
        "plan_code": text(entitlement.get("subscription_plan")),
        "active": boolean(raw.get("is_active")),
        "will_renew": boolean(raw.get("will_renew")),
        "renews_at": timestamp(entitlement.get("renews_at")),
        "expires_at": timestamp(entitlement.get("expires_at")),
        "cancels_at": timestamp(entitlement.get("cancels_at")),
        "period_start": timestamp(raw.get("active_start")),
        "period_end": timestamp(raw.get("active_until")),
        "billing_period": text(entitlement.get("billing_period") or raw.get("billing_period")),
        "currency": text(entitlement.get("billing_currency") or raw.get("billing_currency"), 12),
        "purchase_platform": text(last.get("purchase_origin_platform")),
        "is_delinquent": boolean(raw.get("is_delinquent")),
        "renewal_amount": None,  # Neither price tiers nor historic invoices prove the next charge.
    }


FEATURE_NAMES = {
    "deep_research": "深度研究", "image_gen": "图像生成",
    "voice": "语音", "advanced_voice": "高级语音", "file_upload": "文件上传",
}


def normalize_feature_limits(raw):
    items = []
    progress = raw.get("limits_progress")
    for entry in progress if isinstance(progress, list) else []:
        if not isinstance(entry, dict):
            continue
        feature = text(entry.get("feature_name"))
        if not feature:
            continue
        items.append({"id": feature, "name": FEATURE_NAMES.get(feature, feature),
                      "kind": "feature", "remaining": number(entry.get("remaining")),
                      "resets_at": timestamp(entry.get("reset_after")), "unit": "次"})
    # Model counters are optional. Never infer unlimited from an empty list.
    models = raw.get("model_limits")
    for entry in models if isinstance(models, list) else []:
        if not isinstance(entry, dict):
            continue
        model = text(entry.get("model_slug"))
        if model and "remaining" in entry:
            items.append({"id": "model:"+model, "name": model, "kind": "model",
                          "remaining": number(entry.get("remaining")),
                          "resets_at": timestamp(entry.get("reset_after")), "unit": "次"})
    blocked = raw.get("blocked_features")
    blocked = [text(item) for item in blocked if isinstance(item, str)] if isinstance(blocked, list) else []
    return {"items": items, "blocked_features": blocked,
            "model_counters_provided": any(item["kind"] == "model" for item in items)}


class ChatGPTAccountReader:
    """The OAuth token is read only in memory and sent only to chatgpt.com."""

    def __init__(self, auth_path=None, opener=None):
        self.auth_path = Path(auth_path) if auth_path else Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex"))) / "auth.json"
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.bound_account = None

    def bind_account(self, expected_email):
        _, account_id = self._credentials(expected_email)
        self.bound_account = hashlib.sha256(account_id.encode()).hexdigest()
        return self.bound_account

    def _credentials(self, expected_email):
        try:
            auth = json.loads(self.auth_path.read_text(encoding="utf-8-sig"))
            tokens = auth.get("tokens") or {}
            token, account_id = tokens["access_token"], tokens["account_id"]
            if not isinstance(token, str) or not isinstance(account_id, str) or not token or not account_id:
                raise ValueError("missing credentials")
            # The API validates the token. This local check only prevents mixing identities.
            part = tokens["id_token"].split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(part+"="*(-len(part)%4)))
            email = claims.get("email")
            if not isinstance(expected_email, str) or not isinstance(email, str) or email.casefold() != expected_email.casefold():
                raise ChatGPTSourceError("ChatGPT 登录账户与当前 Codex 账户不一致，请重新登录后刷新。", clear_cache=True)
            return token, account_id
        except ChatGPTSourceError:
            raise
        except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise ChatGPTSourceError("无法读取本机 ChatGPT OAuth 登录，请在 Codex 重新登录后刷新。", clear_cache=True) from None

    def _read(self, resource, expected_email):
        if resource not in ("billing", "limits"):
            raise ValueError("Unknown read-only resource")
        token, account_id = self._credentials(expected_email)
        if self.bound_account is not None and hashlib.sha256(account_id.encode()).hexdigest() != self.bound_account:
            raise ChatGPTSourceError("ChatGPT 账户正在切换，将重新读取订阅数据。", clear_cache=True)
        headers = {"Authorization": "Bearer "+token, "ChatGPT-Account-Id": account_id,
                   "Accept": "application/json", "User-Agent": "TURZX-Studio/1.0"}
        if resource == "billing":
            url = "https://chatgpt.com/backend-api/subscriptions?" + urllib.parse.urlencode({"account_id": account_id})
            request = urllib.request.Request(url, headers=headers, method="GET")
        else:
            # This is the page's quota initialization query. No prompt, message,
            # conversation creation, inference, or quota redemption is submitted.
            headers["Content-Type"] = "application/json"
            request = urllib.request.Request("https://chatgpt.com/backend-api/conversation/init",
                                             data=b"{}", headers=headers, method="POST")
        try:
            with self.opener.open(request, timeout=8) as response:
                body = response.read(512*1024+1)
                if len(body) > 512*1024:
                    raise ChatGPTSourceError("ChatGPT 数据响应异常，已停止本次读取。")
                raw = json.loads(body)
                if not isinstance(raw, dict):
                    raise ChatGPTSourceError("ChatGPT 数据格式已变化，暂时无法读取。")
                if resource == "limits" and not any(key in raw for key in ("limits_progress", "model_limits")):
                    raise ChatGPTSourceError("ChatGPT 额度格式已变化，暂时无法读取。")
                if resource == "billing" and not any(key in raw for key in ("entitlement", "plan_type", "is_active")):
                    raise ChatGPTSourceError("ChatGPT 订阅格式已变化，暂时无法读取。")
                return raw
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403):
                raise ChatGPTSourceError("ChatGPT 账户接口拒绝了登录凭据，请在 Codex 检查登录状态。") from None
            if code == 429:
                raise ChatGPTSourceError("ChatGPT 暂时限制查询频率，将在下一轮重试。") from None
            raise ChatGPTSourceError("ChatGPT 账户接口暂时不可用，将自动重试。") from None
        except (OSError, ValueError, urllib.error.URLError):
            raise ChatGPTSourceError("ChatGPT 数据读取超时或失败，将自动重试。") from None

    def read_limits(self, expected_email):
        return normalize_feature_limits(self._read("limits", expected_email))

    def read_billing(self, expected_email):
        return normalize_billing(self._read("billing", expected_email))
