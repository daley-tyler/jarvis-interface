import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'JARVIS_VOICE_V20'))
import command_router as router
import voice_service as service


class RouterTests(unittest.TestCase):
    def test_supported_actions(self):
        cases = {
            'show Japan': ('country', 'japan'),
            'show New Zealand': ('country', 'new_zealand'),
            'locate America': ('country', 'united_states'),
            'open globe': ('globe', 'open'),
            'hide the globe': ('globe', 'close'),
            'reset globe': ('globe', 'reset'),
            'close identity': ('identity', 'close'),
            'switch to cinematic mode': ('background', 'cinematic'),
            'camera mode': ('background', 'camera'),
            'show diagnostics': ('workspace', 'system'),
            'open hand tracking': ('workspace', 'tracking'),
            'show commands': ('workspace', 'commands'),
            'close workspace': ('workspace', 'close'),
            'reset core': ('core', 'reset'),
            'mute ambient sound': ('ambience', 'mute'),
            'unmute background': ('ambience', 'unmute'),
            'analyze Joey locations': ('joey_scan', 'start'),
            'help': ('none', ''),
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                r = router.route('Jarvis, ' + phrase)
                self.assertEqual((r.command, r.argument), expected)

    def test_rejects_ambiguous_or_negated_instructions(self):
        for phrase in ['do not show Japan', 'never open globe', 'disclose globe',
                       'show Japan and close globe', 'show Japan later', 'unopened globe',
                       'reset core unless tracking', 'open tracking disabled',
                       'I said Jarvis show Japan', 'Jarvisx show Japan']:
            with self.subTest(phrase=phrase):
                self.assertIn(router.route('Jarvis ' + phrase).command, ('none', 'unknown'))

    def test_wake_word_must_be_first(self):
        for text in ['', 'show Japan', 'hello Jarvis show Japan', 'Jarvisx show Japan']:
            self.assertEqual(router.route(text).command, 'none')

    def test_punctuation_and_politeness(self):
        self.assertEqual(router.route('JARVIS! Please show Japan.').argument, 'japan')
        self.assertEqual(router.route('Jarvis, show Japan please').argument, 'japan')

    def test_untrusted_input(self):
        for value in [None, {}, ['Jarvis'], 17, 'Jarvis ' + 'x' * 2000]:
            self.assertEqual(router.route(value).command, 'none')


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stack = contextlib.ExitStack()
        for name, filename in [('ROOT', ''), ('COMMAND_FILE', 'voice_command.json'),
                               ('STATUS_FILE', 'voice_status.json'), ('ACK_FILE', 'voice_ack.json')]:
            self.stack.enter_context(patch.object(service, name, self.root / filename))

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def test_malformed_json_and_wrong_shapes(self):
        for text in ['bad json', '[]', 'null', 'false', '3', '"hello"']:
            (self.root / 'a.json').write_text(text)
            self.assertEqual(service.read_json(self.root / 'a.json', {}), {})

    def test_atomic_packet_and_sequence_recovery(self):
        service.COMMAND_FILE.write_text('{"seq": Infinity}')
        a = service.emit('country', 'japan', 'Jarvis show Japan')
        b = service.emit('country', 'japan', 'Jarvis show Japan')
        self.assertGreater(b['seq'], a['seq'])
        service.COMMAND_FILE.unlink()
        c = service.emit('globe', 'open', 'Jarvis open globe')
        self.assertGreater(c['seq'], b['seq'])
        self.assertEqual(json.loads(service.COMMAND_FILE.read_text()), c)
        self.assertEqual(list(self.root.glob('jarvis_*')), [])

    def test_unknown_command_never_emits(self):
        with patch.object(service, 'emit') as emit, patch.object(service, 'say'):
            service.handle('Jarvis do not show Japan', {}, True)
            emit.assert_not_called()

    def test_no_false_confirmation_when_scene_absent(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = service.handle('Jarvis show Japan', {'ack_timeout': 0}, True)
        self.assertEqual(result.command, 'country')
        self.assertIn('not confirmed', output.getvalue())

    def test_rejected_ack_is_reported(self):
        output = io.StringIO()
        with patch.object(service, 'wait_for_ack', return_value={'ok': False, 'error': 'missing controller'}), contextlib.redirect_stdout(output):
            service.handle('Jarvis show Japan', {}, True)
        self.assertIn('could not complete', output.getvalue())
        self.assertNotIn('missing controller', output.getvalue())

    def test_only_matching_ack_counts(self):
        service.atomic_json(service.ACK_FILE, {'seq': 2, 'ok': True})
        self.assertIsNone(service.wait_for_ack(3, 0))
        self.assertTrue(service.wait_for_ack(2, 0)['ok'])

    def test_single_writer_lock(self):
        with service.service_lock():
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                with service.service_lock():
                    pass
        with service.service_lock():
            pass

    def test_cleanup_on_failure(self):
        with patch.object(service, '_main', side_effect=RuntimeError('model failed')):
            self.assertEqual(service.main([]), 2)
        self.assertEqual(service.read_json(service.STATUS_FILE, {})['phase'], 'idle')

    def test_no_download_or_cloud_for_text(self):
        settings = self.root / 'settings.json'
        settings.write_text('{"ack_timeout": 0}')
        with patch.object(service, 'SETTINGS', settings), patch.object(service, 'ollama_response') as ai:
            self.assertEqual(service.main(['--text', 'Jarvis help', '--no-speak']), 0)
            ai.assert_not_called()

    def test_invalid_settings_fail_before_capture(self):
        settings = self.root / 'settings.json'
        for value in [float('nan'), float('inf'), -1, 99, None]:
            settings.write_text(json.dumps({'record_seconds': value}))
            with patch.object(service, 'SETTINGS', settings):
                self.assertEqual(service.main(['--text', 'Jarvis help', '--no-speak']), 2)

    def test_status_never_persists_free_form_text(self):
        marker = 'SYNTHETIC_PRIVACY_CANARY'
        service.status('error', text=marker, response=marker, error=marker)
        raw = service.STATUS_FILE.read_text()
        self.assertNotIn(marker, raw)
        self.assertEqual(set(json.loads(raw)), {'phase', 'listening', 'speaking', 'error_code', 'updated_at'})

    def test_free_form_status_phase_is_not_persisted(self):
        service.status('SYNTHETIC_PRIVACY_CANARY')
        self.assertNotIn('SYNTHETIC_PRIVACY_CANARY', service.STATUS_FILE.read_text())

    def test_free_form_action_arguments_are_not_persisted(self):
        with self.assertRaises(ValueError):
            service.emit('country', 'SYNTHETIC_PRIVACY_CANARY', '')
        self.assertFalse(service.COMMAND_FILE.exists())

    def test_packet_has_no_transcript(self):
        marker = 'SYNTHETIC_PRIVACY_CANARY'
        service.emit('country', 'japan', marker)
        self.assertNotIn(marker, service.COMMAND_FILE.read_text())
        self.assertNotIn('transcript', service.COMMAND_FILE.read_text())

    def test_unknown_speech_is_neither_logged_nor_forwarded(self):
        marker = 'SYNTHETIC_PRIVACY_CANARY'
        output = io.StringIO()
        with patch('urllib.request.urlopen') as network, contextlib.redirect_stdout(output):
            service.handle('Jarvis ' + marker, {'ollama': {'enabled': True}}, True)
        network.assert_not_called()
        self.assertNotIn(marker, output.getvalue())
        self.assertNotIn(marker, service.STATUS_FILE.read_text())
        self.assertFalse(service.COMMAND_FILE.exists())

    def test_capture_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(RuntimeError, 'disabled'):
            service.record(2)

    def test_default_launch_does_not_open_hardware(self):
        settings = self.root / 'settings.json'
        settings.write_text('{"microphone_enabled": true}')
        with patch.object(service, 'SETTINGS', settings), patch.object(service, 'record') as capture:
            self.assertEqual(service.main([]), 2)
            capture.assert_not_called()

    def test_empty_capture_skips_model(self):
        from unittest.mock import Mock
        model = Mock()
        self.assertEqual(service.transcribe(model, []), '')
        model.transcribe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
