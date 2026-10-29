"""JARVIS V1.4 holographic core gesture controller.

Loaded into a dedicated TouchDesigner Text DAT. Keeps all manipulation
separate from MediaPipe, three identity panels, HUD renderer and base UI.
Coordinates: original render callbacks use 960 x 540, top-left origin.
"""
import math

W, H = 960.0, 540.0
CENTER = (480.0, 270.0)
PINCH = 0.072  # Exactly the existing card threshold.
SCALE_MIN, SCALE_MAX = 0.50, 1.35
CORE_RADIUS = 190.0

_state = {
    'mode': 'idle',  # idle | single | double
    'tx': 0.0, 'ty': 0.0, 'scale': 1.0, 'rotation': 0.0,
    'single_hand': None, 'start_ptr': None, 'start_xy': (0.0, 0.0),
    'pair_start': None, 'pair_xy': (0.0, 0.0),
    'pair_scale': 1.0, 'pair_rotation': 0.0,
    'previous_pinch': False,
}


def _value(chop, chan, default=None):
    if chop is None:
        return default
    try:
        v = float(chop[chan][0])
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _hands(chop):
    out = {}
    for tag in ('h1', 'h2'):
        k = tag + ':pinch_midpoint:'
        x, y, d = (_value(chop, k + key) for key in ('x', 'y', 'distance'))
        if x is None or y is None or d is None or not (-.25 <= x <= 1.25 and -.25 <= y <= 1.25):
            continue
        active = _value(chop, tag + ':hand_active')
        if active is None:
            active = _value(chop, tag + ':active')
        if active is not None and active < 0.5:
            continue
        if active is None and abs(x) < 0.00001 and abs(y) < 0.00001:
            continue
        # Use SAME vertical flip as render_callbacks for correctly aligned cursor.
        out[tag] = (max(0., min(1., x)) * W,
                    (1. - max(0., min(1., y))) * H,
                    d < PINCH)
    return out


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _clamped_xy(x, y, scale):
    # All central graphics remain visible; no accidental off-screen dragging.
    radius = CORE_RADIUS * scale
    cx = _clamp(CENTER[0] + x, radius + 12., W - radius - 12.)
    cy = _clamp(CENTER[1] + y, radius + 12., H - radius - 12.)
    return cx - CENTER[0], cy - CENTER[1]


def _core_hit(point):
    cx = CENTER[0] + _state['tx']
    cy = CENTER[1] + _state['ty']
    x, y = point
    return math.hypot(x - cx, y - cy) <= 204.0 * _state['scale']


def _panel_hit(point, shown, offsets, rects):
    if not shown:
        return False
    px, py = point
    for i, (x, y, w, h) in enumerate(rects):
        try:
            ox, oy = offsets[i]
        except Exception:
            ox, oy = 0., 0.
        if x + ox <= px <= x + ox + w and y + oy <= py <= y + oy + h:
            return True
    return False


def _midpoint_and_angle(a, b):
    mx, my = (a[0] + b[0]) / 2., (a[1] + b[1]) / 2.
    distance = max(1., math.hypot(b[0] - a[0], b[1] - a[1]))
    angle = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    return mx, my, distance, angle


def _set_mode_single(tag, point):
    _state['mode'] = 'single'
    _state['single_hand'] = tag
    _state['start_ptr'] = point[:2]
    _state['start_xy'] = (_state['tx'], _state['ty'])


def _set_mode_double(a, b):
    _state['mode'] = 'double'
    _state['pair_start'] = _midpoint_and_angle(a, b)
    _state['pair_xy'] = (_state['tx'], _state['ty'])
    _state['pair_scale'] = _state['scale']
    _state['pair_rotation'] = _state['rotation']


def _visual_update(hud, mode):
    trans = hud.op('jv14_core_transform')
    feedback = hud.op('jv14_feedback_switch')
    if trans is not None:
        # Transform TOP uses fractional X/Y translation in its default mode.
        # TOP Y points upward; gesture Y is measured downward.
        trans.par.tx = _state['tx'] / W
        trans.par.ty = -_state['ty'] / H
        trans.par.sx = _state['scale']
        trans.par.sy = _state['scale']
        trans.par.rotate = -_state['rotation']
    if feedback is not None:
        feedback.par.index = 2 if mode in ('single', 'double') else (1 if mode == 'hover' else 0)


def update(chop, pointer, pressed, active, panel_dragging, panels_shown,
           panel_offsets, panel_rects, hud):
    """Called once per frame by render_callbacks.onCook.

    Returns True only while the core has captured an actual pinch; existing
    panel dragging/toggle code then receives pressed=False for that frame.
    """
    s = _state
    if not active or panel_dragging >= 0:
        s['mode'] = 'idle'
        s['single_hand'] = None
        s['previous_pinch'] = False
        _visual_update(hud, 'idle')
        return False
    hands = _hands(chop)
    pressed_hands = {tag: p for tag, p in hands.items() if p[2]}
    point = (pointer[0] * W, pointer[1] * H)
    if not pressed_hands and pressed:
        # Compatibility for versions where _get_hand resolves a different prefix.
        pressed_hands = {'legacy': (point[0], point[1], True)}
    two = ('h1' in pressed_hands and 'h2' in pressed_hands)
    primary_tag = next(iter(pressed_hands), None)

    if s['mode'] == 'idle':
        if primary_tag is not None and not s['previous_pinch']:
            # Capture only on NEW pinch, never by sliding a held pinch into core.
            # In all cases identity card hitboxes win over core manipulation.
            is_panel = any(_panel_hit(p[:2], panels_shown, panel_offsets, panel_rects)
                           for p in pressed_hands.values())
            if not is_panel and any(_core_hit(p[:2]) for p in pressed_hands.values()):
                if two:
                    _set_mode_double(pressed_hands['h1'], pressed_hands['h2'])
                else:
                    _set_mode_single(primary_tag, pressed_hands[primary_tag])
        status = 'hover' if s['mode'] == 'idle' and _core_hit(point) else s['mode']
        _visual_update(hud, status)
        s['previous_pinch'] = bool(pressed_hands)
        return s['mode'] != 'idle'

    if not pressed_hands:
        s['mode'] = 'idle'
        s['single_hand'] = None
        _visual_update(hud, 'hover' if _core_hit(point) else 'idle')
        s['previous_pinch'] = False
        return False

    if two and s['mode'] != 'double':
        _set_mode_double(pressed_hands['h1'], pressed_hands['h2'])
    elif not two and s['mode'] == 'double':
        _set_mode_single(primary_tag, pressed_hands[primary_tag])

    if s['mode'] == 'double' and two:
        mx, my, dist, angle = _midpoint_and_angle(pressed_hands['h1'], pressed_hands['h2'])
        mx0, my0, dist0, angle0 = s['pair_start']
        s['scale'] = _clamp(s['pair_scale'] * dist / dist0, SCALE_MIN, SCALE_MAX)
        # Shortest angular difference prevents 360 degree jumps at +/-180.
        da = (angle - angle0 + 180.) % 360. - 180.
        s['rotation'] = s['pair_rotation'] + da
        s['tx'], s['ty'] = _clamped_xy(
            s['pair_xy'][0] + mx - mx0,
            s['pair_xy'][1] + my - my0,
            s['scale'])
    else:
        tag = s['single_hand']
        if tag not in pressed_hands:
            _set_mode_single(primary_tag, pressed_hands[primary_tag])
            tag = primary_tag
        x0, y0 = s['start_ptr']
        x, y = pressed_hands[tag][:2]
        s['tx'], s['ty'] = _clamped_xy(
            s['start_xy'][0] + x - x0,
            s['start_xy'][1] + y - y0,
            s['scale'])

    _visual_update(hud, s['mode'])
    s['previous_pinch'] = bool(pressed_hands)
    return True


def reset():
    """Reset core without touching the identity panel state."""
    _state.update(mode='idle', tx=0., ty=0., scale=1., rotation=0.,
                  single_hand=None, start_ptr=None, previous_pinch=False)
