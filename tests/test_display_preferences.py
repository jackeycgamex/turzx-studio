"""Offline checks for restart-safe local display preferences."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Studio, DISPLAY_PREFERENCES, load_display_preferences, save_display_preferences


class DisplayPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "display-preferences.json"

    def studio(self):
        studio = Studio.__new__(Studio)
        studio.state_lock = threading.RLock()
        studio.preferences_path = self.path
        studio.state = {"subscription_background": "none", "subscription_background_transparency": 25,
                        "rotation": 270, "page": "system", "fps": 2, "focus": {}}
        studio.snapshot = lambda: dict(studio.state)
        return studio

    def test_control_saves_both_preferences_and_retains_zero(self):
        studio = self.studio()
        studio.control({"subscription_background": "dragon"})
        studio.control({"subscription_background_transparency": 0})
        self.assertEqual(load_display_preferences(self.path), {
            "subscription_background": "dragon", "subscription_background_transparency": 0,
            "rotation": 270, "page": "system", "fps": 2})
        studio.control({"subscription_background": "none"})
        self.assertEqual(load_display_preferences(self.path)["subscription_background_transparency"], 0)

    def test_only_requested_preferences_are_saved(self):
        save_display_preferences(self.path, {"subscription_background": "it", "subscription_background_transparency": 100,
                                            "rotation": 0, "page": "openai", "fps": 5,
                                            "streaming": True, "token": "private"})
        self.assertEqual(set(json.loads(self.path.read_text(encoding="utf-8"))),
                         set(DISPLAY_PREFERENCES))

    def test_page_rotation_and_fps_are_saved_together(self):
        studio = self.studio()
        studio.control({"rotation": 0, "page": "openai", "fps": 5})
        saved = load_display_preferences(self.path)
        self.assertEqual((saved['rotation'], saved['page'], saved['fps']), (0, 'openai', 5))
        self.assertEqual(saved['subscription_background'], 'none')

    def test_old_file_and_invalid_new_fields_keep_valid_preferences(self):
        saved = {'subscription_background': 'dragon', 'subscription_background_transparency': 0}
        self.path.write_text(json.dumps(saved), encoding='utf-8')
        self.assertEqual(load_display_preferences(self.path), saved)
        for invalid in ({'rotation': True, 'fps': False, 'page': 'unknown'},
                        {'rotation': 45, 'fps': 3, 'page': []},
                        {'rotation': '90', 'fps': 2.0, 'page': None}):
            self.path.write_text(json.dumps({**saved, **invalid}), encoding='utf-8')
            self.assertEqual(load_display_preferences(self.path), saved)

    def test_auto_rotation_saves_current_page(self):
        studio = self.studio()
        studio.state.update(auto=True, interval=5, subscription_auto=False)
        studio.last_page_at = 0
        studio.focus_deadline = None
        studio.renderer = None
        studio.session_id = 0
        studio.stopping = unittest.mock.Mock()
        studio.stopping.wait.side_effect = [False, True]
        studio._clock()
        self.assertEqual(studio.state['page'], 'network')
        self.assertEqual(load_display_preferences(self.path)['page'], 'network')

    def test_missing_or_broken_file_keeps_defaults(self):
        self.assertEqual(load_display_preferences(self.path), {})
        for body in ('{"broken":', 'null', '[]'):
            self.path.write_text(body, encoding="utf-8")
            with self.assertLogs('turzx', level='WARNING') if body.startswith('{') else self.subTest(body=body):
                self.assertEqual(load_display_preferences(self.path), {})

    def test_invalid_fields_are_ignored_independently(self):
        for value in (-1, 101, True, '20', None):
            self.path.write_text(json.dumps({"subscription_background": "anime", "subscription_background_transparency": value}), encoding="utf-8")
            self.assertEqual(load_display_preferences(self.path), {"subscription_background": "anime"})
        self.path.write_text(json.dumps({"subscription_background": "../secret", "subscription_background_transparency": 50}), encoding="utf-8")
        self.assertEqual(load_display_preferences(self.path), {"subscription_background_transparency": 50})

    def test_failed_replace_preserves_disk_and_memory(self):
        studio = self.studio()
        studio.control({"subscription_background": "it"})
        before = self.path.read_bytes()
        with patch('server.os.replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                studio.control({"subscription_background": "dragon"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(studio.state["subscription_background"], "it")
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
