"""Exercise the actual bridge module with a small TD operator boundary double."""
import json
from pathlib import Path
import runpy
import tempfile
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Parameter:
    def __init__(self, value=0): self.value = value
    def eval(self): return self.value
    def __bool__(self): return bool(self.value)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'JARVIS_VOICE_V20'
        self.root.mkdir()
        self.params = types.SimpleNamespace(Voiceactive=Parameter(), Mute=Parameter())
        self.status_node = types.SimpleNamespace(text='')
        self.ambience = types.SimpleNamespace(par=self.params)
        self.hud = types.SimpleNamespace(path='/project1/gesture_hud',
            op=lambda name: {'jarvis_ambience': self.ambience, 'jv20_voice_status': self.status_node}.get(name))
        self.selected = []
        self.globe = types.SimpleNamespace(_state={'open': False, 'selected': None, 'captured': None},
                                          select=self.select, reset=lambda: None)
        self.space = runpy.run_path(str(ROOT / 'JARVIS_VOICE_V20/JV20_TOUCHDESIGNER_BRIDGE.py'), init_globals={
            'project': types.SimpleNamespace(folder=self.temp.name),
            'op': lambda name: self.hud,
            'mod': lambda path: self.globe})
        self.g = self.space['poll'].__globals__
        self.g['_clock'] = types.SimpleNamespace(time=time.time, monotonic=lambda: self.now)
        self.now = 0
        self.poll(0)  # Attach without replaying prior-session commands.

    def poll(self, frame):
        self.now = frame / 50
        self.space['poll'](frame)

    def tearDown(self): self.temp.cleanup()

    def select(self, i):
        self.selected.append(i)
        self.globe._state['selected'] = i

    def packet(self, seq, command='country', argument='japan', at=None):
        (self.root / 'voice_command.json').write_text(json.dumps({
            'seq': seq, 'command': command, 'argument': argument,
            'at': time.time() if at is None else at}))

    def ack(self): return json.loads((self.root / 'voice_ack.json').read_text())

    def test_real_file_dispatch_and_ack(self):
        self.packet(1)
        self.poll(6)
        self.assertEqual(self.selected, [2])
        self.assertEqual(self.ack()['seq'], 1)
        self.assertTrue(self.ack()['ok'])

    def test_typed_service_and_bridge_complete_a_round_trip(self):
        import contextlib
        import io
        import sys
        import threading
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'JARVIS_VOICE_V20'))
        import voice_service
        output = io.StringIO()
        errors = []
        def send():
            try:
                voice_service.handle('Jarvis show Japan', {'ack_timeout': 2}, True)
            except BaseException as error:
                errors.append(error)
        with patch.object(voice_service, 'COMMAND_FILE', self.root / 'voice_command.json'), \
             patch.object(voice_service, 'STATUS_FILE', self.root / 'voice_status.json'), \
             patch.object(voice_service, 'ACK_FILE', self.root / 'voice_ack.json'), \
             contextlib.redirect_stdout(output):
            sender = threading.Thread(target=send)
            sender.start()
            deadline = time.monotonic() + 3
            frame = 6
            while sender.is_alive() and time.monotonic() < deadline:
                self.poll(frame)
                frame += 6
                time.sleep(.01)
            sender.join(timeout=1)
        self.assertFalse(sender.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.selected, [2])
        self.assertTrue(self.ack()['ok'])
        self.assertNotIn('not confirmed', output.getvalue())
        self.assertNotIn('Jarvis show Japan', (self.root / 'voice_status.json').read_text())

    def test_low_frame_rate_does_not_wait_six_frames(self):
        self.packet(1)
        self.now = 0.05
        self.space['poll'](1)
        self.assertEqual(self.selected, [])
        self.now = 0.5  # Next available frame in a slow scene.
        self.space['poll'](2)
        self.assertEqual(self.selected, [2])

    def test_duplicate_not_executed(self):
        self.packet(1)
        self.poll(6)
        self.poll(12)
        self.assertEqual(self.selected, [2])

    def test_stale_or_future_commands_rejected(self):
        for seq, stamp in enumerate([time.time()-60, time.time()+60, float('nan')], 1):
            self.packet(seq, at=stamp)
            self.poll(seq*6)
            self.assertFalse(self.ack()['ok'])
        self.assertEqual(self.selected, [])

    def test_wrong_arguments_and_unknown_actions_rejected(self):
        for seq, command, arg in [(1, 'country', '../../bad'), (2, 'shell', 'echo hello'), (3, 'ambience', 'bad')]:
            self.packet(seq, command, arg)
            self.poll(seq*6)
            self.assertFalse(self.ack()['ok'])
        self.assertEqual(self.selected, [])

    def test_wrong_status_shapes_do_not_break_polling(self):
        for data in [[], True, 'hi', 42, None]:
            (self.root / 'voice_status.json').write_text(json.dumps(data))
            self.poll(6)
            self.assertIn('waiting', self.status_node.text)

    def test_raw_speech_fields_never_reach_the_saved_status_dat(self):
        marker = 'SYNTHETIC_PRIVACY_CANARY'
        (self.root / 'voice_status.json').write_text(json.dumps({
            'phase': 'idle', 'text': marker, 'response': marker, 'error': marker, 'updated_at': time.time()}))
        self.poll(6)
        self.assertNotIn(marker, self.status_node.text)
        self.assertNotIn('heard', self.status_node.text)
        self.assertNotIn('reply', self.status_node.text)

    def test_stale_status_releases_ducking(self):
        (self.root / 'voice_status.json').write_text(json.dumps({'speaking': True, 'updated_at': time.time()-60}))
        self.params.Voiceactive = Parameter(1)
        self.poll(6)
        self.assertEqual(self.params.Voiceactive, 0)

    def test_tour_yields_to_gesture(self):
        self.packet(1, 'joey_scan', 'start')
        self.poll(6)
        self.globe._state['captured'] = 'spin'
        self.poll(12)
        self.assertIsNone(self.g['_scan'])
        self.assertEqual(self.selected, [0])

    def test_old_packet_ignored_on_attach(self):
        self.g['_seq'] = None
        self.packet(200)
        self.poll(6)
        self.assertEqual(self.selected, [])
        self.packet(201)
        self.poll(12)
        self.assertEqual(self.selected, [2])

    def test_malformed_command_keeps_running(self):
        for data in ['{', 'null', '[]', '{"seq":"bad"}', '{"seq":Infinity}']:
            (self.root / 'voice_command.json').write_text(data)
            self.poll(6)
        self.packet(1)
        self.poll(12)
        self.assertEqual(self.selected, [2])


if __name__ == '__main__': unittest.main()
