"""Shared animation phase: controls and physical display use the same clock."""
from __future__ import annotations

import math
import time

PRESETS = ("orbit", "aurora", "flow", "stars")


class AnimationState:
    """Access under Studio.state_lock. No frame-count-dependent simulation."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._anchor = clock()
        self._phase = 0.0
        self.settings = {"preset": "orbit", "speed": 1.0, "detail": "balanced",
                         "show_clock": True, "paused": False, "seed": 52}

    @staticmethod
    def validate(patch):
        if not isinstance(patch, dict):
            raise ValueError("动画设置必须为对象。")
        if set(patch)-{"preset", "speed", "detail", "show_clock", "paused", "seed"}:
            raise ValueError("未知动画设置。")
        if "preset" in patch and patch["preset"] not in PRESETS:
            raise ValueError("未知动画效果。")
        if "speed" in patch:
            value = patch["speed"]
            if type(value) not in (int, float) or not math.isfinite(value) or not .25 <= value <= 2:
                raise ValueError("动画速度应在 0.25–2 倍之间。")
        if "detail" in patch and patch["detail"] not in ("light", "balanced"):
            raise ValueError("细节应为 light 或 balanced。")
        for key in ("show_clock", "paused"):
            if key in patch and type(patch[key]) is not bool:
                raise ValueError(f"{key} 应为布尔值。")
        if "seed" in patch and (type(patch["seed"]) is not int or not 0 <= patch["seed"] <= 2147483647):
            raise ValueError("图形种子超出范围。")

    def phase(self):
        elapsed = 0 if self.settings["paused"] else (self._clock()-self._anchor)*self.settings["speed"]
        return self._phase+elapsed

    def update(self, patch):
        self.validate(patch)
        self._phase = self.phase()
        self._anchor = self._clock()
        reset = any(key in patch and patch[key] != self.settings[key] for key in ("preset", "seed"))
        self.settings.update(patch)
        if reset:
            self._phase = 0.0

    def snapshot(self):
        return {**self.settings, "time": round(self.phase(), 6)}
