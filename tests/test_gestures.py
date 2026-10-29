import importlib.util
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path(str(ROOT / 'touchdesigner/render_callbacks.py'))

    def hand(self, x=.5, y=.5, distance=.04, active=1):
        return {'h1:pinch_midpoint:x': [x], 'h1:pinch_midpoint:y': [y],
                'h1:pinch_midpoint:distance': [distance], 'h1:hand_active': [active]}

    def test_finite_live_hand(self):
        self.assertEqual(self.module['_get_hand'](self.hand()), (.5, .5, .04))

    def test_absent_or_invalid_hand_is_rejected(self):
        for hand in [None, {}, self.hand(active=0), self.hand(active=float('nan')),
                     self.hand(x=float('nan')), self.hand(y=float('inf')),
                     self.hand(distance=-1), self.hand(distance=float('nan')),
                     self.hand(x=2)]:
            with self.subTest(hand=hand):
                self.assertIsNone(self.module['_get_hand'](hand))

    def test_helper_aliases(self):
        for prefix in ('h0:', 'h2:'):
            self.assertIsNotNone(self.module['_get_hand']({k.replace('h1:', prefix): v for k, v in self.hand().items()}))

    def test_outside_edge_is_clamped(self):
        self.assertEqual(self.module['_get_hand'](self.hand(x=1.1))[0], 1)

    def test_pinch_jitter_and_tracking_loss(self):
        import numpy as np
        from types import SimpleNamespace
        g = self.module['onCook'].__globals__
        held = []
        class Controller:
            _state = {'mode': 'idle', 'captured': None}
            def update(self, **kwargs):
                held.append(kwargs['pressed'])
                return False
        controller = Controller()
        modules = {'jv16_identity_guard': SimpleNamespace(filter_legacy=lambda **kw: kw['pressed']),
                   'hud_draw_runtime': SimpleNamespace(render=lambda **kw: np.zeros((2, 2, 4), np.uint8))}
        settings = {('hand_chop', 1): SimpleNamespace(val='/hands'),
                    ('mode', 1): SimpleNamespace(val='hand')}
        hud = SimpleNamespace(path='/hud', op=lambda _: settings)
        script = SimpleNamespace(parent=lambda: hud, copyNumpyArray=lambda _: None)
        g['absTime'] = SimpleNamespace(seconds=1)
        g['mod'] = lambda path: modules.get(path.split('/')[-1], controller)
        current = self.hand()
        g['op'] = lambda _: current
        values = [.071, .064, .071, .077, .084, .086]
        for value, expected in zip(values, [False, True, True, True, True, False]):
            current['h1:pinch_midpoint:distance'] = [value]
            held.clear()
            self.module['onCook'](script)
            self.assertEqual(held[0], expected)
        current['h1:pinch_midpoint:distance'] = [.04]
        self.module['onCook'](script)
        self.assertTrue(g['_state']['pinch_down'])
        current = None
        self.module['onCook'](script)
        self.assertFalse(g['_state']['pinch_down'])
        self.assertEqual(g['_state']['dragging'], -1)

    def test_globe_projection_and_country_validation(self):
        globe = runpy.run_path(str(ROOT / 'touchdesigner/jv16_globe_controller.py'))
        globe['_state'].update(yaw=0., pitch=0.)
        x, y, depth = globe['project'](0, 0)
        self.assertAlmostEqual(x, 556)
        self.assertAlmostEqual(y, 309)
        self.assertAlmostEqual(depth, 1)
        self.assertIsNone(globe['project'](0, 180))
        with self.assertRaises(ValueError): globe['select'](3)


if __name__ == '__main__': unittest.main()
