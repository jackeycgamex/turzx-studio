"""Small Windows WinUSB transport for the TURZX 1cbe:0050 display.

The transport uses the installed Microsoft driver. It never resets a device,
changes its USB configuration, saves settings or writes device storage.
Protocol reference: usausa/turing-smart-screen, MIT, commit
ade6bd871aa22430b0061eed890f2cd191c3d276. See THIRD_PARTY_LICENSES.txt.

Importing this module does not access hardware. Constructing TurzxWinUSB opens
one device and reads its descriptors, but sends no vendor command.
"""

from __future__ import annotations

import copy
import ctypes as C
from datetime import datetime
from io import BytesIO
import math
import os
import struct
import threading
import time
import uuid


DEVICE_INTERFACE_GUID = "88bae032-5a81-49f0-bc3d-a4ff138216d6"
PACKET_SIZE = 512
MAX_IMAGE_BYTES = 1024 * 1024
TIMEOUT_MS = 2000
DES_KEY = b"slv3tuzx"  # Fixed public vendor-protocol value, not a user credential.
U8, U16, U32 = C.c_uint8, C.c_uint16, C.c_uint32
HANDLE, BOOL = C.c_void_p, C.c_int32
INVALID_HANDLE_VALUE = C.c_void_p(-1).value


class TurzxUSBError(RuntimeError):
    """USB open, transfer, descriptor or device acknowledgement failure."""


class GUID(C.Structure):
    _fields_ = [("Data1", U32), ("Data2", U16), ("Data3", U16), ("Data4", U8 * 8)]


class SP_DEVICE_INTERFACE_DATA(C.Structure):
    _fields_ = [("cbSize", U32), ("InterfaceClassGuid", GUID), ("Flags", U32),
                ("Reserved", C.c_size_t)]


class USB_INTERFACE_DESCRIPTOR(C.Structure):
    _pack_ = 1
    _fields_ = [(field, U8) for field in (
        "bLength", "bDescriptorType", "bInterfaceNumber", "bAlternateSetting",
        "bNumEndpoints", "bInterfaceClass", "bInterfaceSubClass",
        "bInterfaceProtocol", "iInterface")]


class WINUSB_PIPE_INFORMATION(C.Structure):
    _fields_ = [("PipeType", C.c_int32), ("PipeId", U8),
                ("MaximumPacketSize", U16), ("Interval", U8)]


def build_command(command: int, parameters: bytes = b"", *, timestamp_ms=None) -> bytes:
    """Build a vendor command offline; parameters start at byte 8 of plaintext."""
    if not isinstance(command, int) or not 0 <= command <= 255:
        raise ValueError("command must be an integer in [0, 255]")
    parameters = bytes(parameters)
    if len(parameters) > 492:
        raise ValueError("parameters exceed the 500-byte command body")
    if timestamp_ms is None:
        now = datetime.now()
        timestamp_ms = ((now.hour * 60 + now.minute) * 60 + now.second) * 1000 + now.microsecond // 1000
    if not isinstance(timestamp_ms, int) or not 0 <= timestamp_ms < 86_400_000:
        raise ValueError("timestamp_ms must be milliseconds since local midnight")
    from Crypto.Cipher import DES
    body = bytearray(504)
    body[0] = command
    body[2:4] = b"\x1a\x6d"
    struct.pack_into("<I", body, 4, timestamp_ms)
    body[8:8 + len(parameters)] = parameters
    encrypted = DES.new(DES_KEY, DES.MODE_CBC, iv=DES_KEY).encrypt(bytes(body))
    return encrypted + b"\x00" * 6 + b"\xa1\x1a"


def validate_ack(response: bytes, *, command: int) -> bytes:
    """Require the full 512-byte ACK and the documented status byte 0xC8.

    Byte 8 is not treated as a status: storage responses use it for capacity.
    Unknown firmware reply formats fail visibly instead of implying success.
    """
    response = bytes(response)
    if len(response) != PACKET_SIZE or response[1] != 0xC8:
        raise TurzxUSBError(
            f"Command {command}: invalid ACK ({len(response)} bytes, "
            f"prefix={response[:24].hex()}); expected 512 bytes and status[1]=c8")
    return response


class _WindowsAPI:
    def __init__(self):
        if os.name != "nt":
            raise OSError("TurzxWinUSB requires Windows")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.setup = C.WinDLL("setupapi", use_last_error=True)
        self.usb = C.WinDLL("winusb", use_last_error=True)
        signatures = [
            (self.setup, "SetupDiGetClassDevsW", HANDLE, [C.POINTER(GUID), C.c_wchar_p, HANDLE, U32]),
            (self.setup, "SetupDiEnumDeviceInterfaces", BOOL, [HANDLE, C.c_void_p, C.POINTER(GUID), U32, C.POINTER(SP_DEVICE_INTERFACE_DATA)]),
            (self.setup, "SetupDiGetDeviceInterfaceDetailW", BOOL, [HANDLE, C.POINTER(SP_DEVICE_INTERFACE_DATA), C.c_void_p, U32, C.POINTER(U32), C.c_void_p]),
            (self.setup, "SetupDiDestroyDeviceInfoList", BOOL, [HANDLE]),
            (self.kernel, "CreateFileW", HANDLE, [C.c_wchar_p, U32, U32, C.c_void_p, U32, U32, HANDLE]),
            (self.kernel, "CloseHandle", BOOL, [HANDLE]),
            (self.usb, "WinUsb_Initialize", BOOL, [HANDLE, C.POINTER(HANDLE)]),
            (self.usb, "WinUsb_Free", BOOL, [HANDLE]),
            (self.usb, "WinUsb_QueryInterfaceSettings", BOOL, [HANDLE, U8, C.POINTER(USB_INTERFACE_DESCRIPTOR)]),
            (self.usb, "WinUsb_QueryPipe", BOOL, [HANDLE, U8, U8, C.POINTER(WINUSB_PIPE_INFORMATION)]),
            (self.usb, "WinUsb_SetPipePolicy", BOOL, [HANDLE, U8, U32, U32, C.c_void_p]),
            (self.usb, "WinUsb_WritePipe", BOOL, [HANDLE, U8, C.c_void_p, U32, C.POINTER(U32), C.c_void_p]),
            (self.usb, "WinUsb_ReadPipe", BOOL, [HANDLE, U8, C.c_void_p, U32, C.POINTER(U32), C.c_void_p]),
            (self.usb, "WinUsb_GetDescriptor", BOOL, [HANDLE, U8, U8, U16, C.c_void_p, U32, C.POINTER(U32)]),
            (self.usb, "WinUsb_QueryDeviceInformation", BOOL, [HANDLE, U32, C.POINTER(U32), C.c_void_p]),
        ]
        for library, name, result, arguments in signatures:
            fn = getattr(library, name)
            fn.restype, fn.argtypes = result, arguments


def _winerror(operation: str, code=None):
    code = C.get_last_error() if code is None else code
    error = C.WinError(code)
    raise TurzxUSBError(f"{operation}: {error}") from error


def enumerate_device_paths(vid=0x1CBE, pid=0x0050, *, _api=None) -> list[str]:
    """Enumerate current matching interfaces through SetupAPI; no USB open."""
    api = _api or _WindowsAPI()
    guid = GUID.from_buffer_copy(uuid.UUID(DEVICE_INTERFACE_GUID).bytes_le)
    info = api.setup.SetupDiGetClassDevsW(C.byref(guid), None, None, 0x12)
    if info in (None, INVALID_HANDLE_VALUE):
        _winerror("SetupDiGetClassDevsW")
    paths = []
    try:
        index = 0
        while True:
            interface = SP_DEVICE_INTERFACE_DATA()
            interface.cbSize = C.sizeof(interface)
            if not api.setup.SetupDiEnumDeviceInterfaces(info, None, C.byref(guid), index, C.byref(interface)):
                code = C.get_last_error()
                if code == 259:  # ERROR_NO_MORE_ITEMS
                    break
                _winerror("SetupDiEnumDeviceInterfaces", code)
            required = U32()
            ok = api.setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(interface), None, 0, C.byref(required), None)
            if not ok and C.get_last_error() != 122:  # Expected ERROR_INSUFFICIENT_BUFFER
                _winerror("SetupDiGetDeviceInterfaceDetailW(size)")
            if required.value < 6 or required.value > 1024 * 1024:
                raise TurzxUSBError(f"Invalid interface-detail size: {required.value}")
            detail = C.create_string_buffer(required.value)
            U32.from_buffer(detail).value = 8 if C.sizeof(C.c_void_p) == 8 else 6
            if not api.setup.SetupDiGetDeviceInterfaceDetailW(info, C.byref(interface), detail, required, None, None):
                _winerror("SetupDiGetDeviceInterfaceDetailW(data)")
            # cbSize is 8 on x64, but the WCHAR DevicePath starts at offset 4.
            path = detail.raw[4:].decode("utf-16-le").split("\x00", 1)[0]
            match = path.casefold()
            if f"vid_{vid:04x}&pid_{pid:04x}" in match:
                paths.append(path)
            index += 1
    finally:
        api.setup.SetupDiDestroyDeviceInfoList(info)
    return list(dict.fromkeys(paths))


class TurzxWinUSB:
    """Exclusive command owner for one panel; supports context-manager cleanup."""

    def __init__(self, vid=0x1CBE, pid=0x0050, serial=None):
        self._api = _WindowsAPI()
        self._file = None
        self._handle = HANDLE()
        self._lock = threading.RLock()
        self._faulted = False
        self._info = {}
        self.vid, self.pid = int(vid), int(pid)
        paths = enumerate_device_paths(vid, pid, _api=self._api)
        if serial is not None:
            # The descriptor is verified after opening, as well as this filter.
            paths = [p for p in paths if f"#{str(serial).casefold()}#" in p.casefold()]
        if not paths:
            raise TurzxUSBError(f"No present WinUSB interface for {vid:04x}:{pid:04x}" + (f" serial={serial}" if serial else ""))
        if len(paths) != 1:
            raise TurzxUSBError(f"Found {len(paths)} matching panels; specify serial to avoid selecting the wrong device")
        self.device_path = paths[0]
        try:
            self._file = self._api.kernel.CreateFileW(self.device_path, 0xC0000000, 3, None, 3, 0x40000080, None)
            if self._file in (None, INVALID_HANDLE_VALUE):
                self._file = None
                _winerror("CreateFileW (panel may be busy in another app)")
            if not self._api.usb.WinUsb_Initialize(self._file, C.byref(self._handle)):
                _winerror("WinUsb_Initialize (panel may be busy in another app)")
            self._query_pipes()
            self._info = self._read_descriptors()
            if self._info["vendor_id"] != self.vid or self._info["product_id"] != self.pid:
                raise TurzxUSBError("Opened USB descriptor does not match the requested VID/PID")
            if serial is not None and self._info.get("serial_number", "").casefold() != str(serial).casefold():
                raise TurzxUSBError("Opened USB serial descriptor does not match requested serial")
        except BaseException:
            self.close()
            raise

    def _query_pipes(self):
        interface = USB_INTERFACE_DESCRIPTOR()
        if not self._api.usb.WinUsb_QueryInterfaceSettings(self._handle, 0, C.byref(interface)):
            _winerror("WinUsb_QueryInterfaceSettings")
        if interface.bInterfaceNumber != 0:
            raise TurzxUSBError(f"Unexpected interface {interface.bInterfaceNumber}; expected interface 0")
        self._interface = {name: int(getattr(interface, name)) for name, _ in interface._fields_}
        self._pipes = []
        for index in range(interface.bNumEndpoints):
            pipe = WINUSB_PIPE_INFORMATION()
            if not self._api.usb.WinUsb_QueryPipe(self._handle, 0, index, C.byref(pipe)):
                _winerror("WinUsb_QueryPipe")
            self._pipes.append({"address": int(pipe.PipeId), "address_hex": f"0x{pipe.PipeId:02x}",
                                "type": int(pipe.PipeType), "direction": "in" if pipe.PipeId & 0x80 else "out",
                                "max_packet_size": int(pipe.MaximumPacketSize), "interval": int(pipe.Interval)})
        inbound = [p for p in self._pipes if p["type"] == 2 and p["direction"] == "in"]
        outbound = [p for p in self._pipes if p["type"] == 2 and p["direction"] == "out"]
        if len(inbound) != 1 or len(outbound) != 1:
            raise TurzxUSBError("Expected exactly one bulk IN and one bulk OUT endpoint")
        self._in, self._out = inbound[0]["address"], outbound[0]["address"]
        for pipe_id in (self._in, self._out):
            self._set_timeout(pipe_id, TIMEOUT_MS)

    def _set_timeout(self, pipe_id, timeout_ms):
        value = U32(timeout_ms)
        if not self._api.usb.WinUsb_SetPipePolicy(self._handle, pipe_id, 3, C.sizeof(value), C.byref(value)):
            _winerror("WinUsb_SetPipePolicy(PIPE_TRANSFER_TIMEOUT)")

    def _get_descriptor(self, kind, index=0, language=0, size=255):
        buffer = C.create_string_buffer(size)
        count = U32()
        if not self._api.usb.WinUsb_GetDescriptor(self._handle, kind, index, language, buffer, size, C.byref(count)):
            _winerror(f"WinUsb_GetDescriptor(type={kind}, index={index})")
        if count.value < 2 or count.value > size:
            raise TurzxUSBError("USB descriptor has invalid returned length")
        result = buffer.raw[:count.value]
        if result[1] != kind:
            raise TurzxUSBError("USB descriptor type mismatch")
        return result

    def _read_descriptors(self):
        device = self._get_descriptor(1, size=18)
        if len(device) != 18 or device[0] != 18:
            raise TurzxUSBError("USB device descriptor must be 18 bytes")
        values = struct.unpack("<BBHBBBBHHHBBBB", device)
        names = ("length", "descriptor_type", "bcd_usb", "device_class", "device_subclass", "device_protocol",
                 "ep0_max_packet_size", "vendor_id", "product_id", "bcd_device", "manufacturer_index",
                 "product_index", "serial_index", "configuration_count")
        info = dict(zip(names, values))
        info.update({"device_path": self.device_path, "device_descriptor_hex": device.hex(),
                     "interface": self._interface, "endpoints": self._pipes, "warnings": [],
                     "bcd_usb_hex": f"0x{info['bcd_usb']:04x}", "bcd_device_hex": f"0x{info['bcd_device']:04x}"})
        if self.pid == 0x0050:
            info["inferred_panel"] = {"model": "TURZX 5.2 inch USB", "native_width": 720, "native_height": 1280,
                                      "basis": "public project VID/PID mapping; not returned by USB descriptor"}
        try:
            languages = self._get_descriptor(3)
            if len(languages) < languages[0] or languages[0] < 4 or languages[0] % 2:
                raise TurzxUSBError("Invalid USB language descriptor")
            language_ids = list(struct.unpack("<" + "H" * ((languages[0] - 2) // 2), languages[2:languages[0]]))
            info["language_ids"] = language_ids
            language = 0x0409 if 0x0409 in language_ids else language_ids[0]
        except TurzxUSBError as exc:
            info["warnings"].append(str(exc))
            language = 0x0409
        for key, index_key in (("manufacturer", "manufacturer_index"), ("product", "product_index"), ("serial_number", "serial_index")):
            info[key] = ""
            if not info[index_key]:
                continue
            try:
                raw = self._get_descriptor(3, info[index_key], language)
                if raw[0] > len(raw) or raw[0] < 2 or raw[0] % 2:
                    raise TurzxUSBError(f"Invalid {key} string descriptor")
                info[key] = raw[2:raw[0]].decode("utf-16-le")
            except (TurzxUSBError, UnicodeError) as exc:
                info["warnings"].append(str(exc))
        try:
            head = self._get_descriptor(2, size=9)
            if len(head) != 9:
                raise TurzxUSBError("Configuration header must be 9 bytes")
            total_length = struct.unpack_from("<H", head, 2)[0]
            if not 9 <= total_length <= 65535:
                raise TurzxUSBError("Invalid configuration total length")
            configuration = self._get_descriptor(2, size=total_length)
            if len(configuration) != total_length:
                raise TurzxUSBError("Truncated configuration descriptor")
            info["configuration"] = {"total_length": total_length, "interface_count": head[4], "value": head[5],
                                     "attributes": head[7], "self_powered": bool(head[7] & 0x40),
                                     "remote_wakeup": bool(head[7] & 0x20),
                                     "declared_max_power_ma": head[8] * (8 if info["bcd_usb"] >= 0x0300 else 2),
                                     "descriptor_hex": configuration.hex()}
        except TurzxUSBError as exc:
            info["warnings"].append(str(exc))
        speed = U8()
        length = U32(C.sizeof(speed))
        if self._api.usb.WinUsb_QueryDeviceInformation(self._handle, 1, C.byref(length), C.byref(speed)):
            info["speed_code"] = speed.value
            info["speed"] = {1: "full-speed or lower", 2: "full-speed", 3: "high-speed or higher"}.get(speed.value, "unknown")
        else:
            info["warnings"].append(f"WinUsb_QueryDeviceInformation failed: Windows error {C.get_last_error()}")
        return info

    def descriptor_info(self) -> dict:
        """Return a copy of descriptors cached during construction; no new I/O."""
        return copy.deepcopy(self._info)

    def _ensure_open(self):
        if not self._handle.value:
            raise TurzxUSBError("Panel is closed")
        if self._faulted:
            raise TurzxUSBError("Previous transfer failed; close and explicitly reconnect before another command")

    def _transact(self, command: int, parameters=b"", payload=b"") -> bytes:
        packet = build_command(command, parameters) + payload
        with self._lock:
            self._ensure_open()
            try:
                buffer = C.create_string_buffer(packet, len(packet))
                count = U32()
                if not self._api.usb.WinUsb_WritePipe(self._handle, self._out, buffer, len(packet), C.byref(count), None):
                    _winerror(f"WinUsb_WritePipe(command={command})")
                if count.value != len(packet):
                    raise TurzxUSBError(f"Short USB write: {count.value}/{len(packet)} bytes")
                deadline = time.monotonic() + TIMEOUT_MS / 1000
                # A USB zero-length packet is transport framing, not a vendor
                # response. At most two such reads; the command is never resent.
                for _ in range(3):
                    remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
                    self._set_timeout(self._in, remaining_ms)
                    response = C.create_string_buffer(PACKET_SIZE)
                    count = U32()
                    if not self._api.usb.WinUsb_ReadPipe(self._handle, self._in, response, PACKET_SIZE, C.byref(count), None):
                        _winerror(f"WinUsb_ReadPipe(command={command})")
                    if count.value:
                        return validate_ack(response.raw[:count.value], command=command)
                    if time.monotonic() >= deadline:
                        break
                raise TurzxUSBError(f"Command {command}: no ACK after zero-length USB packets")
            except BaseException:
                self._faulted = True
                raise

    def sync(self) -> bytes:
        return self._transact(10)

    @staticmethod
    def _check_image(data: bytes, expected_format: str):
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"Image must contain 1..{MAX_IMAGE_BYTES} bytes")
        from PIL import Image
        with Image.open(BytesIO(data)) as image:
            if image.format != expected_format:
                raise ValueError(f"Expected {expected_format}, got {image.format}")
            if image.size != (720, 1280):
                raise ValueError(f"Expected a native portrait frame 720x1280; received {image.size}")
            if expected_format == "PNG" and image.mode != "RGBA":
                raise ValueError("TURZX PNG overlay requires RGBA (color type 6); RGB PNG can ACK but render incorrectly")
            if expected_format == "JPEG" and image.info.get("progressive"):
                raise ValueError("Progressive JPEG is not supported; use baseline JPEG")
            image.verify()

    def draw_png(self, image: bytes) -> bytes:
        image = bytes(image)
        self._check_image(image, "PNG")
        return self._transact(102, struct.pack(">I", len(image)), image)

    def draw_jpeg(self, image: bytes) -> bytes:
        image = bytes(image)
        self._check_image(image, "JPEG")
        return self._transact(101, struct.pack(">I", len(image)), image)

    def brightness(self, percent) -> bytes:
        percent = float(percent)
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError("brightness must be in [0, 100]")
        return self._transact(14, bytes([int(percent / 100 * 102)]))

    def storage_info(self) -> dict:
        response = self._transact(100)
        total, used, available = struct.unpack_from("<III", response, 8)
        return {"total_raw": total, "used_raw": used, "available_raw": available,
                "unit": "vendor units; not independently verified", "response_hex": response.hex()}

    def close(self):
        """Release only this process's handles; do not reset or blank the panel."""
        with self._lock:
            if self._handle.value:
                self._api.usb.WinUsb_Free(self._handle)
                self._handle = HANDLE()
            if self._file not in (None, INVALID_HANDLE_VALUE):
                self._api.kernel.CloseHandle(self._file)
                self._file = None

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
