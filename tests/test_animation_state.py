import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from animation_state import AnimationState


class AnimationClockTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.motion = AnimationState(lambda: self.now)

    def test_pause_and_resume_preserve_phase(self):
        self.now += 3
        self.motion.update({"paused": True})
        self.now += 100
        self.assertEqual(self.motion.phase(), 3)
        self.motion.update({"paused": False})
        self.now += 2
        self.assertEqual(self.motion.phase(), 5)

    def test_speed_change_does_not_jump(self):
        self.now += 4
        self.motion.update({"speed": .5})
        self.assertEqual(self.motion.phase(), 4)
        self.now += 6
        self.assertEqual(self.motion.phase(), 7)

    def test_invalid_patch_is_atomic(self):
        before = self.motion.snapshot()
        for patch in ({"speed": math.nan}, {"speed": True}, {"preset": "missing"}, {"paused": 1}, {"seed": -1}, {"time": 12}):
            with self.assertRaises(ValueError):
                self.motion.update(patch)
            self.assertEqual(self.motion.snapshot(), before)

    def test_new_seed_and_effect_restart_consistently(self):
        self.now += 8
        self.motion.update({"seed": 53})
        self.assertEqual(self.motion.phase(), 0)
        self.now += 2
        self.motion.update({"preset": "aurora"})
        self.assertEqual(self.motion.snapshot()["time"], 0)


if __name__ == "__main__":
    unittest.main()
