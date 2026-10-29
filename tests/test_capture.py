"""Capture and push-to-talk wiring checks with synthetic audio and fake devices."""
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'JARVIS_VOICE_V20'))
import voice_service as service
import voice_panel


class CaptureTests(unittest.TestCase):
    def stream(self, *, stop=None, overflow=False):
        class Stream:
            reads = 0
            closed = False
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def read(self, frames):
                self.reads += 1
                if stop is not None and self.reads == 2: stop.set()
                return np.zeros((frames, 1), dtype=np.float32), overflow
        return Stream()

    def capture(self, stream, **kwargs):
        fake = types.SimpleNamespace(InputStream=lambda **options: stream)
        with patch.dict(sys.modules, sounddevice=fake):
            return service.record(2, microphone_allowed=True, **kwargs)

    def test_bounded_capture_uses_synthetic_blocks(self):
        stream = self.stream()
        samples = self.capture(stream)
        self.assertEqual(samples.shape, (32000,))
        self.assertEqual(stream.reads, 20)
        self.assertTrue(stream.closed)
        self.assertFalse(np.any(samples))

    def test_stop_ends_capture_and_closes_stream(self):
        stop = threading.Event()
        stream = self.stream(stop=stop)
        samples = self.capture(stream, stop=stop)
        self.assertEqual(samples.shape, (3200,))
        self.assertEqual(stream.reads, 2)
        self.assertTrue(stream.closed)

    def test_overflow_closes_stream_without_returning_audio(self):
        stream = self.stream(overflow=True)
        with self.assertRaisesRegex(RuntimeError, 'overflow'):
            self.capture(stream)
        self.assertTrue(stream.closed)


class PanelTests(unittest.TestCase):
    def run_scenario(self, close_during_capture):
        callbacks = []
        workers = []
        recorded = []
        handled = []
        states = []
        button = None

        class Widget:
            def __init__(self, *args, **kwargs):
                nonlocal button
                self.command = kwargs.get('command')
                if self.command: button = self
            def pack(self): pass
            def config(self, **kwargs): pass
        class Variable:
            def __init__(self, **kwargs): pass
            def set(self, value): states.append(value)
        class Window:
            destroyed = False
            def title(self, value): pass
            def geometry(self, value): pass
            def after(self, delay, callback): callbacks.append(callback)
            def protocol(self, name, callback): self.close = callback
            def destroy(self): self.destroyed = True
            def mainloop(self):
                button.command()  # Speak queues one worker.
                if close_during_capture: self.close()
                else: button.command()  # Stop before that worker starts.
                self.assert_single_worker()
                workers[0]()
                callbacks.pop(0)()
                if not close_during_capture: self.close()
            def assert_single_worker(self):
                if len(workers) != 1: raise AssertionError('Repeated click created another worker')
        class Worker:
            def __init__(self, *, target, daemon): workers.append(target)
            def start(self): pass
        def record(seconds, **kwargs):
            recorded.append((kwargs['stop'].is_set(), kwargs['microphone_allowed']))
            return np.zeros(1600, dtype=np.float32)
        fake_service = types.SimpleNamespace(record=record, transcribe=lambda *args: 'Jarvis show Japan',
            handle=lambda *args: handled.append(args), status=lambda *args, **kwargs: None)
        window = Window()
        fake_tk = types.SimpleNamespace(Tk=lambda: window, StringVar=Variable, Label=Widget, Button=Widget)
        with patch.dict(sys.modules, tkinter=fake_tk), patch.object(voice_panel.threading, 'Thread', Worker):
            voice_panel.run_panel(object(), {'record_seconds': 2, 'microphone_enabled': False}, fake_service, True)
        self.assertEqual(recorded, [(True, False)])
        self.assertTrue(window.destroyed)
        return handled

    def test_stop_reuses_worker_and_propagates_capture_guard(self):
        self.assertEqual(len(self.run_scenario(False)), 1)

    def test_close_stops_capture_and_suppresses_dispatch(self):
        self.assertEqual(self.run_scenario(True), [])


if __name__ == '__main__': unittest.main()
