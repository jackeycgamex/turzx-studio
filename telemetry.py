"""Low-overhead, read-only Windows telemetry for TURZX Studio.

All sizes exposed as *_gb use GiB (1024**3). Rates named *_bps are
bytes per second for the existing frontend contract, not bits per second.
Missing data is None. No temperature, fan or power values are fabricated.
"""
from __future__ import annotations

import copy
import ctypes as ct
from ctypes import wintypes as wt
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
import json
import os
import platform
import re
import subprocess
import threading
import time
import uuid

import psutil

GIB = 1024 ** 3
SHANGHAI = timezone(timedelta(hours=8))


def _host_identity():
    """One bounded startup query. PhysicalAdapter alone includes VPNs on Windows."""
    script = (
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();"
        "$c=Get-CimInstance Win32_Processor|Select-Object -First 1;"
        "$n=@(Get-CimInstance Win32_NetworkAdapter|Where-Object {"
        "$_.PNPDeviceID -match '^(PCI|USB)\\\\' -and $_.NetConnectionID"
        "}|Select-Object -ExpandProperty NetConnectionID);"
        "@{cpu=$c.Name;interfaces=$n}|ConvertTo-Json -Compress"
    )
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW, check=True,
            )
            data = json.loads(result.stdout.lstrip("\ufeff"))
            names = data.get("interfaces", [])
            if isinstance(names, str):
                names = [names]
            return data.get("cpu") or platform.processor(), set(names), "Windows PnP PCI/USB"
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    # Never silently add tunnels when physical-adapter identification failed.
    return platform.processor() or "CPU", set(), "physical interfaces unavailable"


def _dxgi_adapter():
    """Return the first hardware DXGI adapter, including 64-bit VRAM and LUID."""
    if os.name != "nt":
        return None

    class GUID(ct.Structure):
        _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
                    ("Data4", wt.BYTE * 8)]

    class LUID(ct.Structure):
        _fields_ = [("LowPart", wt.DWORD), ("HighPart", wt.LONG)]

    class DESC(ct.Structure):
        _fields_ = [("Description", wt.WCHAR * 128), ("VendorId", wt.UINT),
                    ("DeviceId", wt.UINT), ("SubSysId", wt.UINT), ("Revision", wt.UINT),
                    ("DedicatedVideoMemory", ct.c_size_t),
                    ("DedicatedSystemMemory", ct.c_size_t),
                    ("SharedSystemMemory", ct.c_size_t), ("AdapterLuid", LUID),
                    ("Flags", wt.UINT)]

    def method(obj, index, restype, *args):
        address = ct.cast(obj, ct.POINTER(ct.POINTER(ct.c_void_p))).contents[index]
        return ct.WINFUNCTYPE(restype, ct.c_void_p, *args)(address)

    factory = ct.c_void_p()
    dxgi = ct.WinDLL("dxgi.dll")
    create = dxgi.CreateDXGIFactory1
    create.argtypes = [ct.POINTER(GUID), ct.POINTER(ct.c_void_p)]
    create.restype = ct.c_long
    iid = GUID.from_buffer_copy(uuid.UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
    if create(ct.byref(iid), ct.byref(factory)) < 0:
        return None
    adapters = []
    try:
        enum = method(factory, 12, ct.c_long, wt.UINT, ct.POINTER(ct.c_void_p))
        for index in range(16):
            adapter = ct.c_void_p()
            if enum(factory, index, ct.byref(adapter)) < 0:
                break
            try:
                desc = DESC()
                if method(adapter, 10, ct.c_long, ct.POINTER(DESC))(adapter, ct.byref(desc)) >= 0:
                    if not desc.Flags & 2 and desc.VendorId in (0x1002, 0x10DE, 0x8086):
                        adapters.append({
                            "name": desc.Description,
                            "memory_total_gb": desc.DedicatedVideoMemory / GIB,
                            "luid": f"luid_0x{desc.AdapterLuid.HighPart & 0xffffffff:08x}_"
                                    f"0x{desc.AdapterLuid.LowPart:08x}",
                        })
            finally:
                method(adapter, 2, wt.ULONG)(adapter)
    finally:
        method(factory, 2, wt.ULONG)(factory)
    return max(adapters, key=lambda a: a["memory_total_gb"], default=None)


class _GpuPdh:
    """Persistent PDH query, matched to the DXGI hardware adapter by its LUID."""

    class ValueUnion(ct.Union):
        _fields_ = [("doubleValue", ct.c_double), ("largeValue", ct.c_longlong)]

    class Value(ct.Structure):
        pass

    Value._anonymous_ = ("value",)
    Value._fields_ = [("CStatus", wt.DWORD), ("value", ValueUnion)]

    class Item(ct.Structure):
        pass

    Item._fields_ = [("szName", wt.LPWSTR), ("FmtValue", Value)]

    def __init__(self):
        self.adapter = _dxgi_adapter()
        if not self.adapter:
            raise RuntimeError("No hardware DXGI adapter identified")
        self.dll = ct.WinDLL("pdh.dll")
        self.query = ct.c_void_p()
        self.counters = {}
        signatures = {
            "PdhOpenQueryW": ([wt.LPCWSTR, ct.c_size_t, ct.POINTER(ct.c_void_p)], wt.LONG),
            "PdhAddEnglishCounterW": ([ct.c_void_p, wt.LPCWSTR, ct.c_size_t,
                                       ct.POINTER(ct.c_void_p)], wt.LONG),
            "PdhCollectQueryData": ([ct.c_void_p], wt.LONG),
            "PdhGetFormattedCounterArrayW": ([ct.c_void_p, wt.DWORD,
                                               ct.POINTER(wt.DWORD), ct.POINTER(wt.DWORD),
                                               ct.c_void_p], wt.LONG),
            "PdhCloseQuery": ([ct.c_void_p], wt.LONG),
        }
        for name, (args, ret) in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, ret
        if self.dll.PdhOpenQueryW(None, 0, ct.byref(self.query)) != 0:
            raise RuntimeError("Cannot open GPU PDH query")
        try:
            for key, path in {
                "usage": r"\GPU Engine(*)\Utilization Percentage",
                "memory": r"\GPU Adapter Memory(*)\Dedicated Usage",
            }.items():
                handle = ct.c_void_p()
                status = self.dll.PdhAddEnglishCounterW(self.query, path, 0, ct.byref(handle))
                if status != 0:
                    raise RuntimeError(f"Cannot open GPU {key} counter: {status & 0xffffffff:08x}")
                self.counters[key] = handle
            self.dll.PdhCollectQueryData(self.query)
        except Exception:
            self.close()
            raise

    def _values(self, key):
        size, count = wt.DWORD(), wt.DWORD()
        flags = 0x00000200 | 0x00008000  # PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        fn = self.dll.PdhGetFormattedCounterArrayW
        status = fn(self.counters[key], flags, ct.byref(size), ct.byref(count), None)
        if status & 0xffffffff != 0x800007D2 or not size.value:  # PDH_MORE_DATA
            raise RuntimeError(f"GPU {key} has no valid counter data")
        # Wildcards can grow between the two calls; allow one bounded retry.
        for _ in range(2):
            buffer = ct.create_string_buffer(size.value)
            status = fn(self.counters[key], flags, ct.byref(size), ct.byref(count), buffer)
            if status == 0:
                rows = ct.cast(buffer, ct.POINTER(self.Item))
                return [(rows[i].szName, rows[i].FmtValue.doubleValue)
                        for i in range(count.value) if rows[i].FmtValue.CStatus in (0, 1)]
            if status & 0xffffffff != 0x800007D2:
                break
        raise RuntimeError(f"GPU {key} counter read failed")

    def sample(self):
        if self.dll.PdhCollectQueryData(self.query) != 0:
            raise RuntimeError("GPU counter collection failed")
        luid = self.adapter["luid"]
        engines = defaultdict(float)
        for name, value in self._values("usage"):
            if luid not in name.lower():
                continue
            match = re.search(r"phys_(\d+)_eng_(\d+)", name, re.I)
            if match:
                engines[match.groups()] += max(0.0, value)
        memory = [value for name, value in self._values("memory") if luid in name.lower()]
        return {
            "name": self.adapter["name"],
            "percent": round(min(100.0, max(engines.values())), 1) if engines else None,
            "memory_used_gb": round(sum(memory) / GIB, 3) if memory else None,
            "memory_total_gb": round(self.adapter["memory_total_gb"], 3),
            "source": "DXGI adapter LUID + Windows PDH busiest engine",
            "status": "live" if engines and memory else "unavailable",
        }

    def close(self):
        if self.query:
            self.dll.PdhCloseQuery(self.query)
            self.query = None


class Telemetry:
    """Call snapshot() freely; all hardware reads run in background samplers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._updated = None
        self._gpu_updated = None
        self._cpu_history = deque(maxlen=60)
        self._up_history = deque(maxlen=60)
        self._down_history = deque(maxlen=60)
        self._last_network = None
        self._last_disks = -float("inf")
        self._identity = (platform.processor() or "CPU", set(), "initializing")
        self._data = {
            "timestamp": None, "status": "initializing", "age_ms": None,
            "cpu": {"name": self._identity[0], "percent": None,
                    "cores": psutil.cpu_count(logical=False), "logical": psutil.cpu_count(),
                    "frequency_mhz": None, "frequency_source": "not measured",
                    "history": []},
            "memory": {"percent": None, "used_gb": None, "total_gb": None},
            "disks": [],
            "network": {"sent_bps": None, "recv_bps": None,
                        "total_sent_gb": None, "total_recv_gb": None,
                        "history_up": [], "history_down": [], "interfaces": [],
                        "source": "initializing"},
            "gpu": {"name": "GPU", "percent": None, "memory_used_gb": None,
                    "memory_total_gb": None, "source": "Windows PDH", "status": "initializing"},
            "uptime_s": None, "temperature_c": None,
            "unavailable": ["temperature", "fan", "power", "cpu_frequency"],
            "errors": {},
        }
        self._threads = [threading.Thread(target=self._run, name="turzx-telemetry", daemon=True),
                         threading.Thread(target=self._gpu_run, name="turzx-gpu", daemon=True)]
        for thread in self._threads:
            thread.start()

    def _run(self):
        self._identity = _host_identity()
        psutil.cpu_percent(None)  # Discard meaningless first nonblocking sample.
        primed = False
        while not self._stop.is_set():
            started = time.monotonic()
            changes, errors = {}, {}
            try:
                value = psutil.cpu_percent(None)
                value = float(value) if primed else None
                primed = True
                if value is not None:
                    self._cpu_history.append(value)
                changes["cpu"] = {"name": self._identity[0], "percent": value,
                                  "cores": psutil.cpu_count(logical=False),
                                  "logical": psutil.cpu_count(), "frequency_mhz": None,
                                  "frequency_source": "not measured", "history": list(self._cpu_history)}
            except Exception as exc:
                errors["cpu"] = str(exc)
                with self._lock:
                    changes["cpu"] = dict(self._data["cpu"], percent=None)
            try:
                mem = psutil.virtual_memory()
                changes["memory"] = {"percent": mem.percent, "used_gb": round(mem.used / GIB, 2),
                                     "total_gb": round(mem.total / GIB, 2)}
            except Exception as exc:
                errors["memory"] = str(exc)
                changes["memory"] = {"percent": None, "used_gb": None, "total_gb": None}
            try:
                now = time.monotonic()
                counts, stats = psutil.net_io_counters(pernic=True), psutil.net_if_stats()
                names = sorted(self._identity[1])
                interfaces = [{"name": n, "up": stats[n].isup, "speed_mbps": stats[n].speed}
                              for n in names if n in stats]
                available = {n: counts[n] for n in names if n in counts}
                sent = sum(v.bytes_sent for v in available.values()) if available else None
                recv = sum(v.bytes_recv for v in available.values()) if available else None
                up = down = None
                if available and self._last_network:
                    last_time, last = self._last_network
                    elapsed = now - last_time
                    if elapsed > 0 and set(available) == set(last):
                        delta_up = [v.bytes_sent - last[n].bytes_sent for n, v in available.items()]
                        delta_down = [v.bytes_recv - last[n].bytes_recv for n, v in available.items()]
                        if all(v >= 0 for v in delta_up + delta_down):
                            up, down = sum(delta_up) / elapsed, sum(delta_down) / elapsed
                self._last_network = (now, available)
                if up is not None:
                    self._up_history.append(round(up, 1))
                    self._down_history.append(round(down, 1))
                changes["network"] = {"sent_bps": round(up, 1) if up is not None else None,
                                      "recv_bps": round(down, 1) if down is not None else None,
                                      "total_sent_gb": round(sent / GIB, 3) if sent is not None else None,
                                      "total_recv_gb": round(recv / GIB, 3) if recv is not None else None,
                                      "history_up": list(self._up_history),
                                      "history_down": list(self._down_history),
                                      "interfaces": interfaces, "source": self._identity[2]}
            except Exception as exc:
                errors["network"] = str(exc)
                with self._lock:
                    changes["network"] = dict(self._data["network"], sent_bps=None, recv_bps=None)
            if started - self._last_disks >= 30:
                self._last_disks = started
                disks = []
                try:
                    for partition in psutil.disk_partitions(all=False):
                        if partition.fstype.upper() not in ("NTFS", "REFS", "FAT32", "EXFAT"):
                            continue
                        if "cdrom" in partition.opts.lower() or partition.device.startswith("\\\\"):
                            continue
                        # Only fixed local drives; exclude removable and mapped network devices.
                        if os.name == "nt" and ct.windll.kernel32.GetDriveTypeW(partition.mountpoint) != 3:
                            continue
                        try:
                            usage = psutil.disk_usage(partition.mountpoint)
                            disks.append({"drive": partition.device.rstrip("\\/"), "percent": usage.percent,
                                          "used_gb": round(usage.used / GIB, 1),
                                          "total_gb": round(usage.total / GIB, 1)})
                        except OSError as exc:
                            errors[f"disk:{partition.device}"] = str(exc)
                    changes["disks"] = disks
                except Exception as exc:
                    errors["disks"] = str(exc)
                    changes["disks"] = []
            try:
                changes["uptime_s"] = max(0, round(time.time() - psutil.boot_time()))
            except Exception as exc:
                errors["uptime"] = str(exc)
                changes["uptime_s"] = None
            changes["timestamp"] = datetime.now(SHANGHAI).isoformat(timespec="seconds")
            changes["status"] = "partial" if errors else "live"
            with self._lock:
                self._data.update(changes)
                self._data["errors"] = errors
                self._updated = time.monotonic()
            self._stop.wait(max(0.05, 1 - (time.monotonic() - started)))

    def _gpu_run(self):
        query = None
        try:
            if os.name != "nt":
                raise RuntimeError("Windows GPU counters unavailable on this platform")
            query = _GpuPdh()
            while not self._stop.wait(2):
                try:
                    data = query.sample()
                except Exception as exc:
                    data = {"name": query.adapter["name"], "percent": None,
                            "memory_used_gb": None,
                            "memory_total_gb": query.adapter["memory_total_gb"],
                            "source": "Windows PDH", "status": "unavailable", "error": str(exc)}
                with self._lock:
                    self._data["gpu"] = data
                    self._gpu_updated = time.monotonic()
        except Exception as exc:
            with self._lock:
                self._data["gpu"].update(status="unavailable", error=str(exc))
        finally:
            if query:
                query.close()

    def snapshot(self):
        with self._lock:
            result = copy.deepcopy(self._data)
            updated, gpu_updated = self._updated, self._gpu_updated
        now = time.monotonic()
        result["age_ms"] = round((now - updated) * 1000) if updated else None
        if updated and now - updated > 5:
            result["status"] = "stale"
            result["cpu"]["percent"] = None
            result["memory"].update(percent=None, used_gb=None)
            result["network"].update(sent_bps=None, recv_bps=None)
        if gpu_updated and now - gpu_updated > 6:
            result["gpu"].update(percent=None, memory_used_gb=None, status="stale")
        return result

    def close(self):
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=1)


if __name__ == "__main__":
    telemetry = Telemetry()
    try:
        for _ in range(5):
            time.sleep(1.1)
            print(json.dumps(telemetry.snapshot(), ensure_ascii=False))
    finally:
        telemetry.close()
