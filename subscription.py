"""Read-only ChatGPT account/limits through the installed Codex app-server.

Codex owns login and refresh. The ChatGPT reader uses the local OAuth token in
memory only. No inference, billing mutations, reset redemption or credential copies.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time

from chatgpt_account import ChatGPTAccountReader, ChatGPTSourceError


POLL_SECONDS = 60
STALE_SECONDS = 180


class SourceError(Exception):
    """A safe, user-facing error, without remote payloads or credentials."""


def codex_executable():
    explicit = os.environ.get("TURZX_CODEX_PATH")
    if explicit:
        path = Path(explicit)
        if path.is_file() and path.suffix.lower() == ".exe":
            return str(path)
        raise SourceError("TURZX_CODEX_PATH 必须指向已安装的 codex.exe。")
    direct = shutil.which("codex.exe")
    if direct:
        return direct
    roots = []
    command = shutil.which("codex")
    if command:
        roots.append(Path(command).parent / "node_modules/@openai/codex")
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "npm/node_modules/@openai/codex")
    for root in roots:
        matches = sorted(root.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
        if matches:
            return str(matches[0])
    raise SourceError("未找到 Codex CLI。请安装并登录 Codex 后重新刷新。")


class CodexAccountClient:
    """An owned stdio process with bounded requests; never connects to the app daemon."""

    METHODS = {"account/read", "account/rateLimits/read"}

    def __init__(self, cancelled=None):
        self.process = None
        self.messages = None
        self.serial = 0
        self.cancelled = cancelled or threading.Event()

    def _send(self, message):
        try:
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()
        except (OSError, ValueError, AttributeError):
            raise SourceError("Codex 数据连接已断开，将自动重试。") from None

    def _request(self, method, params, timeout=20):
        self.serial += 1
        request_id = self.serial
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            if self.cancelled.is_set():
                raise SourceError("订阅同步已停止。")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceError("读取 OpenAI 数据超时，将自动重试。")
            try:
                item = self.messages.get(timeout=min(remaining, .25))
            except queue.Empty:
                continue
            if item is None:
                raise SourceError("Codex 数据进程已退出，将自动重试。")
            if item.get("id") == request_id:
                if "error" in item:
                    # Do not expose raw errors, which may include account details.
                    raise SourceError("OpenAI 数据读取失败；请检查网络及 Codex 登录状态。")
                result = item.get("result")
                if not isinstance(result, dict):
                    raise SourceError("OpenAI 返回了无法识别的数据。")
                return result
            if "method" in item and "id" in item:
                # This reader never supplies external auth tokens or approves actions.
                self._send({"id": item["id"], "error": {"code": -32601, "message": "Read-only client"}})

    def _start(self):
        self.close()
        if self.cancelled.is_set():
            raise SourceError("订阅同步已停止。")
        self.messages = queue.Queue(maxsize=256)
        try:
            self.process = subprocess.Popen(
                [codex_executable(), "app-server", "--stdio"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            raise SourceError("无法启动 Codex 数据进程。请检查 Codex CLI 安装。") from None
        process, messages = self.process, self.messages

        def read():
            try:
                for line in process.stdout:
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict):
                            messages.put_nowait(item)
                    except (ValueError, queue.Full):
                        continue
            except (OSError, ValueError):
                pass
            finally:
                try:
                    messages.put_nowait(None)
                except queue.Full:
                    pass

        threading.Thread(target=read, name="subscription-rpc", daemon=True).start()
        self._request("initialize", {"clientInfo": {
            "name": "turzx_studio", "title": "TURZX Studio", "version": "1.0.0",
        }})
        self._send({"method": "initialized", "params": {}})

    def request(self, method, params=None):
        if method not in self.METHODS:
            raise ValueError("Only read-only account methods are permitted")
        try:
            if self.process is None or self.process.poll() is not None:
                self._start()
            return self._request(method, params or {})
        except SourceError:
            self.close()
            raise

    def close(self):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # Only kill descendants of the process created above, never the desktop app.
            import psutil
            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.Error:
                        pass
                parent.kill()
                psutil.wait_procs(children + [parent], timeout=2)
            except psutil.Error:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        if process.stdout:
            process.stdout.close()


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def short_text(value, limit=100):
    return value[:limit] if isinstance(value, str) and value else None


def mask_email(value):
    if not isinstance(value, str) or "@" not in value:
        return None
    local, domain = value.rsplit("@", 1)
    return f"{local[:1]}•••@{domain[:80]}"


def normalize_limits(result):
    """Keep absence, zero and unlimited distinct; never double-count legacy buckets."""
    buckets = result.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict):
        legacy = result.get("rateLimits")
        buckets = {legacy.get("limitId") or "codex": legacy} if isinstance(legacy, dict) else {}
    normalized = []
    for key, raw in buckets.items():
        if not isinstance(raw, dict):
            continue
        windows = []
        for role in ("primary", "secondary"):
            window = raw.get(role)
            if not isinstance(window, dict):
                continue
            used = window.get("usedPercent")
            used = max(0, min(100, used)) if finite_number(used) else None
            minutes = window.get("windowDurationMins")
            minutes = minutes if finite_number(minutes) and minutes > 0 else None
            resets = window.get("resetsAt")
            resets = resets if finite_number(resets) and 0 < resets < 253402300800 else None
            windows.append({"role": role, "used_percent": used,
                            "remaining_percent": None if used is None else 100-used,
                            "duration_minutes": minutes, "resets_at": resets})
        credits = raw.get("credits")
        credit_data = None
        if isinstance(credits, dict):
            balance = credits.get("balance")
            try:
                decimal = Decimal(str(balance))
                balance = str(decimal) if decimal.is_finite() and decimal >= 0 else None
            except (InvalidOperation, ValueError):
                balance = None
            credit_data = {"balance": balance, "unlimited": credits.get("unlimited") is True,
                           "has_credits": credits.get("hasCredits") if type(credits.get("hasCredits")) is bool else None}
        normalized.append({"id": short_text(raw.get("limitId")) or str(key)[:100],
                           "name": short_text(raw.get("limitName")),
                           "plan_type": short_text(raw.get("planType")), "windows": windows,
                           "credits": credit_data, "limit_reached": short_text(raw.get("rateLimitReachedType")),
                           "spend_control_reached": raw.get("spendControlReached") is True})
    reset_info = result.get("rateLimitResetCredits")
    count = reset_info.get("availableCount") if isinstance(reset_info, dict) else None
    count = count if type(count) is int and count >= 0 else None
    return {"buckets": normalized, "reset_count": count}


class SubscriptionMonitor:
    """One polling worker; snapshots are instant and contain only display-safe fields."""

    def __init__(self, client=None, clock=time.time, autostart=True, web_client=None):
        self.stopping = threading.Event()
        self.client = client or CodexAccountClient(self.stopping)
        self.web_client = web_client or ChatGPTAccountReader()
        self.clock = clock
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.identity = None
        self.web_identity = None
        self.last_attempt = 0
        self.force_chatgpt = False
        self.data = {"status": "loading", "account": None, "buckets": [], "reset_count": None,
                     "observed_at": None, "account_observed_at": None, "error": None,
                     "refreshing": False, "poll_seconds": POLL_SECONDS, "stale_seconds": STALE_SECONDS,
                     "source": "Codex app-server · OpenAI",
                     "billing": self._empty_source("ChatGPT 订阅", 1800, 3600),
                     "chatgpt_feature_limits": self._empty_source("ChatGPT 功能额度", 60, 180)}
        self.worker = None
        if autostart:
            self.worker = threading.Thread(target=self._run, name="subscription-monitor", daemon=True)
            self.worker.start()

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.data)
        observed = result["observed_at"]
        if observed is not None and self.clock() - observed > STALE_SECONDS:
            result["status"] = "stale"
        for field in ("billing", "chatgpt_feature_limits"):
            source = result[field]
            if source.get("observed_at") is not None and self.clock()-source["observed_at"] > source["stale_seconds"]:
                source["status"] = "stale"
        return result

    @staticmethod
    def _empty_source(name, interval, stale, status="loading"):
        return {"source": name, "poll_seconds": interval, "stale_seconds": stale,
                "status": status, "observed_at": None, "error": None}

    def refresh(self):
        # Coalesced and rate-limited by the worker, including repeated UI clicks.
        with self.lock:
            self.force_chatgpt = True
        self.wake.set()

    def _poll(self):
        with self.lock:
            self.data["refreshing"] = True
            force_chatgpt, self.force_chatgpt = self.force_chatgpt, False
        try:
            result = self.client.request("account/read", {"refreshToken": False})
            account = result.get("account")
            identity = hashlib.sha256(json.dumps(account, sort_keys=True).encode()).hexdigest()
            with self.lock:
                if identity != self.identity:
                    self.data.update(account=None, buckets=[], reset_count=None, observed_at=None,
                                     account_observed_at=None, status="loading")
                    self.identity = identity
                    self.data["billing"] = self._empty_source("ChatGPT 订阅", 1800, 3600)
                    self.data["chatgpt_feature_limits"] = self._empty_source("ChatGPT 功能额度", 60, 180)
                if not isinstance(account, dict) or account.get("type") not in ("chatgpt", "chatgptAuthTokens"):
                    self.data.update(status="disconnected", error="请先在本机 Codex 登录 ChatGPT 订阅账户。")
                    self.data["billing"]["status"] = "disconnected"
                    self.data["chatgpt_feature_limits"]["status"] = "disconnected"
                    return
                self.data["account"] = {"plan_type": short_text(account.get("planType")),
                                        "email": mask_email(account.get("email")), "auth_type": "chatgpt"}
                self.data["account_observed_at"] = self.clock()
            try:
                result = self.client.request("account/rateLimits/read")
                normalized = normalize_limits(result)
                with self.lock:
                    self.data.update(normalized, observed_at=self.clock(), status="live", error=None)
            except Exception as exc:
                self._codex_error(exc)
            self._poll_chatgpt(account.get("email"), force_chatgpt)
        except Exception as exc:
            # Unexpected local exceptions are also sanitized, never copied into logs/UI.
            self._codex_error(exc)
        finally:
            with self.lock:
                self.data["refreshing"] = False

    def _codex_error(self, exc):
        message = str(exc) if isinstance(exc, SourceError) else "订阅数据暂时不可用，将自动重试。"
        with self.lock:
            self.data.update(status="stale" if self.data["observed_at"] is not None else "error", error=message)

    def _poll_chatgpt(self, email, force):
        try:
            identity = self.web_client.bind_account(email)
        except Exception as exc:
            self._web_error_all(exc)
            return
        with self.lock:
            if identity != self.web_identity:
                self.data["billing"] = self._empty_source("ChatGPT 订阅", 1800, 3600)
                self.data["chatgpt_feature_limits"] = self._empty_source("ChatGPT 功能额度", 60, 180)
                self.web_identity = identity
        for field, read in (("chatgpt_feature_limits", self.web_client.read_limits),
                            ("billing", self.web_client.read_billing)):
            if self.stopping.is_set():
                break
            with self.lock:
                old = copy.deepcopy(self.data[field])
            observed = old.get("observed_at")
            if not force and old["status"] == "live" and observed is not None and self.clock()-observed < old["poll_seconds"]:
                continue
            try:
                values = read(email)
                source = {**values, "source": old["source"], "poll_seconds": old["poll_seconds"],
                          "stale_seconds": old["stale_seconds"], "observed_at": self.clock(),
                          "status": "live", "error": None}
            except Exception as exc:
                clear = isinstance(exc, ChatGPTSourceError) and exc.clear_cache
                if clear:
                    self._web_error_all(exc)
                    return
                source = old
                source.update(status="stale" if source.get("observed_at") is not None else "error",
                              error=str(exc) if isinstance(exc, ChatGPTSourceError) else "ChatGPT 数据暂时不可用，将自动重试。")
            with self.lock:
                self.data[field] = source

    def _web_error_all(self, exc):
        clear = isinstance(exc, ChatGPTSourceError) and exc.clear_cache
        message = str(exc) if isinstance(exc, ChatGPTSourceError) else "ChatGPT 账户来源暂时不可用，将自动重试。"
        with self.lock:
            for field in ("billing", "chatgpt_feature_limits"):
                old = self.data[field]
                source = self._empty_source(old["source"], old["poll_seconds"], old["stale_seconds"]) if clear else old
                source.update(status="stale" if source.get("observed_at") is not None else "error", error=message)
                self.data[field] = source

    def _run(self):
        try:
            while not self.stopping.is_set():
                self.wake.clear()
                self.last_attempt = time.monotonic()
                self._poll()
                self.wake.wait(POLL_SECONDS)
                delay = max(0, 10 - (time.monotonic() - self.last_attempt))
                if self.stopping.wait(delay):
                    break
        finally:
            self.client.close()

    def close(self):
        self.stopping.set()
        self.wake.set()
        if self.worker:
            # Cancellation interrupts RPC waits; only the worker owns process cleanup.
            self.worker.join(timeout=20)
        else:
            self.client.close()
