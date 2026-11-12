"""Lifecycle tests without USB hardware, browsers or account access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Studio, load_display_preferences, SessionPaused


class StreamingResumeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / 'display-preferences.json'
        for name in ('Telemetry', 'SubscriptionMonitor', 'threading.Thread', 'shutil.which',
                     'subprocess.Popen', 'TurzxWinUSB'):
            patcher = patch('server.' + name)
            setattr(self, name.split('.')[-1], patcher.start())
            self.addCleanup(patcher.stop)
        patcher = patch('server.RUNTIME', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.SubscriptionMonitor.return_value.snapshot.return_value = {}
        self.TurzxWinUSB.return_value.descriptor_info.return_value = {}
        self.which.return_value = 'node'

    def create(self, resume=None):
        if resume is not None:
            self.path.write_text(json.dumps({'resume_streaming': resume}), encoding='utf-8')
        app = Studio(8765)
        self.addCleanup(app.close)
        return app

    def test_old_settings_do_not_start_usb(self):
        app = self.create()
        app.resume_on_startup()
        self.TurzxWinUSB.assert_not_called()
        self.assertFalse(app.state['streaming'])

    def test_saved_state_is_not_reported_as_connected_before_resume(self):
        app = self.create(True)
        self.assertFalse(app.state['streaming'])
        self.assertFalse(app.state['connected'])
        app.resume_on_startup()
        app.resume_on_startup()
        self.TurzxWinUSB.assert_called_once()
        self.assertTrue(app.state['streaming'])

    def test_close_preserves_resume_but_explicit_stop_clears_it(self):
        app = self.create()
        app.start()
        app.close()
        self.assertTrue(load_display_preferences(self.path)['resume_streaming'])
        next_app = self.create()
        next_app.resume_on_startup()
        next_app.control({'action': 'stop'})
        next_app.close()
        self.assertFalse(load_display_preferences(self.path)['resume_streaming'])
        self.assertFalse(next_app.state['streaming'])

    def test_stop_before_resume_cancels_pending_start(self):
        app = self.create(True)
        app.control({'action': 'stop'})
        app.resume_on_startup()
        self.TurzxWinUSB.assert_not_called()

    def test_shutdown_releases_usb_before_returning_and_preserves_resume(self):
        app = self.create()
        app.start()
        response = app.control({'action': 'shutdown'})
        self.assertTrue(app.stopping.is_set())
        self.assertFalse(response['streaming'])
        self.assertFalse(response['connected'])
        self.assertIsNone(app.device)
        self.assertTrue(load_display_preferences(self.path)['resume_streaming'])

    def test_missing_usb_only_attempts_once_and_keeps_manual_retry_available(self):
        app = self.create(True)
        self.TurzxWinUSB.side_effect = OSError('USB unavailable')
        with self.assertLogs('turzx', level='WARNING'):
            app.resume_on_startup()
        app.resume_on_startup()
        self.TurzxWinUSB.assert_called_once()
        self.assertFalse(app.state['streaming'])
        self.assertFalse(app.state['connected'])
        self.assertEqual(app.snapshot()['error'], 'USB unavailable')
        self.assertTrue(load_display_preferences(self.path)['resume_streaming'])
        self.TurzxWinUSB.side_effect = None
        app.control({'action': 'start'})
        self.assertTrue(app.state['streaming'])

    def test_failed_first_start_does_not_enable_resume(self):
        app = self.create()
        self.Popen.side_effect = OSError('renderer unavailable')
        with self.assertRaises(OSError):
            app.start()
        self.assertFalse(app.state['streaming'])
        self.assertFalse(app.state['resume_streaming'])
        self.TurzxWinUSB.return_value.close.assert_called()

    def test_stale_session_stop_cannot_clear_new_resume_setting(self):
        app = self.create()
        app.start()
        app.stop(expected_session=app.session_id-1, remember=True)
        self.assertTrue(app.state['streaming'])
        self.assertTrue(load_display_preferences(self.path)['resume_streaming'])

    def test_closed_service_cannot_resume_or_start(self):
        app = self.create(True)
        app.close()
        app.resume_on_startup()
        with self.assertRaises(SessionPaused):
            app.start()
        self.TurzxWinUSB.assert_not_called()

    def test_resume_setting_requires_a_boolean(self):
        for invalid in ('true', 1, None, []):
            self.path.write_text(json.dumps({'resume_streaming': invalid}), encoding='utf-8')
            self.assertNotIn('resume_streaming', load_display_preferences(self.path))


if __name__ == '__main__':
    unittest.main()
