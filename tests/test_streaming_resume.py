"""Lifecycle tests without USB hardware, browsers or account access."""
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Studio, load_display_preferences, SessionPaused


class StreamingResumeTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.path = self.root / 'display-preferences.json'
        for name in ('Telemetry', 'SubscriptionMonitor', 'threading.Thread', 'shutil.which',
                     'subprocess.Popen', 'TurzxWinUSB', 'enumerate_device_paths'):
            patcher = patch('server.' + name)
            setattr(self, name.split('.')[-1], patcher.start())
            self.addCleanup(patcher.stop)
        patcher = patch('server.RUNTIME', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.SubscriptionMonitor.return_value.snapshot.return_value = {}
        self.TurzxWinUSB.return_value.descriptor_info.return_value = {}
        self.which.return_value = 'node'
        self.enumerate_device_paths.return_value = ['panel']

    def create(self, resume=None):
        if resume is not None:
            self.path.write_text(json.dumps({'resume_streaming': resume}), encoding='utf-8')
        app = Studio(8765)
        self.addCleanup(app.close)
        return app

    def test_old_settings_do_not_start_usb(self):
        app = self.create()
        app.try_resume_streaming()
        self.TurzxWinUSB.assert_not_called()
        self.assertFalse(app.state['streaming'])

    def test_saved_state_is_not_reported_as_connected_before_resume(self):
        app = self.create(True)
        self.assertFalse(app.state['streaming'])
        self.assertFalse(app.state['connected'])
        app.try_resume_streaming()
        app.try_resume_streaming()
        self.TurzxWinUSB.assert_called_once()
        self.assertTrue(app.state['streaming'])

    def test_close_preserves_resume_but_explicit_stop_clears_it(self):
        app = self.create()
        app.start()
        app.close()
        self.assertTrue(load_display_preferences(self.path)['resume_streaming'])
        next_app = self.create()
        next_app.try_resume_streaming()
        next_app.control({'action': 'stop'})
        next_app.close()
        self.assertFalse(load_display_preferences(self.path)['resume_streaming'])
        self.assertFalse(next_app.state['streaming'])

    def test_stop_before_resume_cancels_pending_start(self):
        app = self.create(True)
        app.control({'action': 'stop'})
        app.try_resume_streaming()
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

    def test_failed_reconnect_is_throttled_and_keeps_manual_retry_available(self):
        app = self.create(True)
        self.TurzxWinUSB.side_effect = OSError('USB unavailable')
        with self.assertLogs('turzx', level='WARNING'):
            app.try_resume_streaming()
        app.try_resume_streaming()
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
        app.try_resume_streaming()
        with self.assertRaises(SessionPaused):
            app.start()
        self.TurzxWinUSB.assert_not_called()

    def test_resume_setting_requires_a_boolean(self):
        for invalid in ('true', 1, None, []):
            self.path.write_text(json.dumps({'resume_streaming': invalid}), encoding='utf-8')
            self.assertNotIn('resume_streaming', load_display_preferences(self.path))

    def test_absent_device_is_not_opened_and_replug_resumes(self):
        app = self.create(True)
        self.enumerate_device_paths.return_value = []
        with patch('server.time.monotonic', return_value=100):
            app.try_resume_streaming()
        self.TurzxWinUSB.assert_not_called()
        self.assertFalse(app.state['streaming'])
        self.enumerate_device_paths.return_value = ['panel']
        with patch('server.time.monotonic', return_value=102):
            app.try_resume_streaming()
        self.assertTrue(app.state['streaming'])
        self.TurzxWinUSB.assert_called_once()

    def test_transfer_failure_reconnects_without_late_cleanup_killing_it(self):
        app = self.create()
        app.start()
        old_session = app.session_id
        with self.assertLogs('turzx', level='ERROR'):
            app.fail('USB unplugged', old_session)
        app.try_resume_streaming()
        self.assertGreater(app.session_id, old_session)
        self.assertTrue(app.state['streaming'])
        app.stop(expected_session=old_session)
        self.assertTrue(app.state['streaming'])
        self.assertIsNotNone(app.device)

    def test_repeated_connect_errors_back_off_and_stop_cancels_retries(self):
        app = self.create(True)
        self.TurzxWinUSB.side_effect = OSError('device busy')
        with patch('server.time.monotonic', return_value=100), self.assertLogs('turzx', level='WARNING'):
            app.try_resume_streaming()
        self.assertEqual(app.reconnect_at, 102)
        with patch('server.time.monotonic', return_value=101):
            app.try_resume_streaming()
        self.assertEqual(self.TurzxWinUSB.call_count, 1)
        with patch('server.time.monotonic', return_value=102), self.assertLogs('turzx', level='WARNING'):
            app.try_resume_streaming()
        self.assertEqual(app.reconnect_at, 106)
        app.control({'action': 'stop'})
        with patch('server.time.monotonic', return_value=200):
            app.try_resume_streaming()
        self.assertEqual(self.TurzxWinUSB.call_count, 2)

    def test_successful_usb_frame_resets_backoff(self):
        app = self.create()
        app.start()
        app.reconnect_delay = 30
        app.reconnect_at = 10000
        self.TurzxWinUSB.return_value.draw_png.return_value = b'ack'
        image = Image.new('RGB', (1280,720))
        body = io.BytesIO()
        image.save(body, 'PNG')
        app.frame(body.getvalue(), 270, app.session_id, 0)
        self.assertEqual(app.reconnect_delay, 2)
        self.assertEqual(app.reconnect_at, 0)


if __name__ == '__main__':
    unittest.main()
