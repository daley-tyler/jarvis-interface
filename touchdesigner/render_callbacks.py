"""TouchDesigner Script TOP callback. Installed by BUILD_IN_TOUCHDESIGNER.py."""
import math
import numpy as np

_state = {
    'start': -1.0,
    'visible': 0.0,
    'shown': False,
    'pressed': False,
    'pinch_down': False,
    'dragging': -1,
    'drag_origin': (0.,0.),
    'offset_origin': (0.,0.),
    'offsets': [[0.,0.] for _ in range(3)],
    'last_change': -20.,
    'pointer': (.45, .46),
}

PANEL_RECTS = [(40, 172, 192, 190), (728, 111, 192, 190), (728, 318, 192, 190)]

def _setting(dat, key, default=''):
    try:
        return str(dat[key, 1].val)
    except Exception:
        return default

def _val(chop, chan, default=None):
    if chop is None:
        return default
    try:
        v = chop[chan]
        if v is None:
            return default
        return float(v[0])
    except Exception:
        return default

def _get_hand(chop):
    if chop is None:
        return None
    for prefix in ('h1:', 'h0:', 'h2:'):
        x=_val(chop, prefix+'pinch_midpoint:x')
        y=_val(chop, prefix+'pinch_midpoint:y')
        d=_val(chop, prefix+'pinch_midpoint:distance')
        if x is None or y is None or d is None:
            continue
        if not math.isfinite(x) or not math.isfinite(y) or not math.isfinite(d):
            continue
        active=_val(chop,prefix+'hand_active')
        if active is None: active=_val(chop,prefix+'active')
        if d < 0:
            continue
        if active is not None and (not math.isfinite(active) or active < .5):
            continue
        if not (-.25 <= x <= 1.25 and -.25 <= y <= 1.25):
            continue
        if active is None and abs(x)<1.e-5 and abs(y)<1.e-5:
            continue
        # Webcam coords are top-left origin in MediaPipe plugin.
        return (max(0.,min(1.,x)), max(0.,min(1.,y)), d)
    return None

def _get_face(chop):
    if chop is None:
        return None
    # Different MediaPipe TouchDesigner versions use different channel naming.
    for prefix in ('f0:', 'f1:', ''):
        for center in ('nose_tip:', 'nose:', 'noseTip:', 'landmark_1:', '1:'):
            x=_val(chop,prefix+center+'x')
            y=_val(chop,prefix+center+'y')
            if x is not None and y is not None and 0 <= x <=1 and 0 <= y <=1:
                return (x,y)
    return None

def onCook(scriptOp):
    global _state
    me_hud = scriptOp.parent()
    settings = me_hud.op('settings')
    sec = absTime.seconds
    if _state['start'] < 0:
        _state['start'] = sec
    t = max(0.0, sec-_state['start'])
    hand_source = _setting(settings,'hand_chop')
    mode = _setting(settings,'mode','auto').lower()
    chop = op(hand_source) if hand_source else None
    hand = _get_hand(chop)
    tracking_ready = bool(hand_source and chop is not None)
    allow_demo = (mode=='demo') or (mode=='auto' and not tracking_ready)
    active = hand is not None and mode != 'demo'
    ptr = _state['pointer']
    pressed = False
    if active:
        ptr = (hand[0], 1.0 - hand[1])
        # Separate pinch thresholds avoid jitter repeatedly grabbing/releasing.
        pressed = hand[2] < (.085 if _state['pinch_down'] else .065)
        _state['pinch_down'] = pressed
        _state['pointer'] = ptr
        _state['shown'] = bool(_state['shown'])
    elif allow_demo:
        _state['pinch_down'] = False
        ptr=(.50+.11*math.sin(t*.7), .46+.12*math.cos(t*.51))
        _state['pointer']=ptr
        _state['shown'] = (int(t / 5.5) % 3 != 0)
        _state['pressed'] = False
        _state['dragging'] = -1
    else:
        # Connected tracker, temporarily no hand: stay in last state.
        _state['pinch_down'] = False
        _state['pressed'] = False
        _state['dragging'] = -1

    # V1.6: Globe gestures take priority only when beginning on globe controls.
    jv16_claimed = mod(me_hud.path + '/jv16_globe_controller').update(
        hud=me_hud, chop=chop, pointer=ptr, pressed=pressed, active=active,
        sec=sec, panel_dragging=_state['dragging'],
        core_mode=mod(me_hud.path + '/jv14_core_controller')._state['mode'],
        workspace_capture=mod(me_hud.path + '/jv15_workspace_controller')._state['captured'])
    if jv16_claimed:
        pressed = False

    # JARVIS V1.5: interactive workspaces get first right of refusal,
    # but existing photo cards and any active V1.4 core grab retain priority.
    jv15_claimed = mod(me_hud.path + '/jv15_workspace_controller').update(
        hud=me_hud, chop=chop, pointer=ptr, pressed=pressed, active=active,
        panel_dragging=_state['dragging'], panels_shown=_state['shown'],
        panel_offsets=_state['offsets'], panel_rects=PANEL_RECTS,
        core_mode=mod(me_hud.path + '/jv14_core_controller')._state['mode'])
    if jv15_claimed:
        pressed = False

    # JARVIS V1.4: Core gets a pinch only if the gesture began over the core.
    # The original card controller below remains untouched, and panel hits win.
    jv14_claimed = (not jv16_claimed) and mod(me_hud.path + '/jv14_core_controller').update(
        chop=chop, pointer=ptr, pressed=pressed, active=(active and not jv15_claimed),
        panel_dragging=_state['dragging'], panels_shown=_state['shown'],
        panel_offsets=_state['offsets'], panel_rects=PANEL_RECTS, hud=me_hud)
    if jv14_claimed:
        pressed = False

    # V1.6.3: Only globe markers/rows may open identity images.
    pressed = mod(me_hud.path + '/jv16_identity_guard').filter_legacy(
        chop=chop, pressed=pressed, active=active, sec=sec,
        pointer=ptr, dragging=_state['dragging'])

    if active:
        if pressed and not _state['pressed'] and sec-_state['last_change'] >= .40:
            px,py = ptr[0]*960,ptr[1]*540
            hit = -1
            if _state['shown']:
                for i,(x,y,w,h) in reversed(list(enumerate(PANEL_RECTS))):
                    ox,oy=_state['offsets'][i]
                    if x+ox<=px<=x+ox+w and y+oy<=py<=y+oy+h:
                        hit = i
                        break
            if hit>=0:
                _state['dragging']=hit
                _state['drag_origin']=(px,py)
                _state['offset_origin']=tuple(_state['offsets'][hit])
            else:
                _state['shown']=not _state['shown']
                _state['last_change']=sec
        if pressed and _state['dragging'] >= 0:
            i=_state['dragging']
            px,py=ptr[0]*960,ptr[1]*540
            origx,origy=_state['drag_origin']
            oldx,oldy=_state['offset_origin']
            x,y,w,h=PANEL_RECTS[i]
            ox = max(26-x, min(960-26-(x+w), oldx+px-origx))
            oy = max(74-y, min(540-26-(y+h), oldy+py-origy))
            _state['offsets'][i]=[ox,oy]
        if not pressed:
            _state['dragging']=-1
        _state['pressed']=pressed

    target=1.0 if _state['shown'] else 0.0
    _state['visible'] += (target-_state['visible'])*.16
    if abs(_state['visible']-target)<.002:
        _state['visible']=target
    f_source = _setting(settings,'face_chop')
    face = _get_face(op(f_source) if f_source else None)
    if face is None:
        face=(.5+.07*math.sin(.65*t),.5+.07*math.cos(.51*t))
    asset_dir = _setting(settings,'assets_dir','')
    image = mod(me_hud.path+'/hud_draw_runtime').render(
        t=t, asset_dir=asset_dir,
        pointer=ptr, visible=_state['visible'],
        panel_offsets=_state['offsets'],tracking=active,
        grabbed=_state['dragging'],face=face)
    # Script TOP image axes may be inverted relative to our top-left coordinates.
    flip = _setting(settings,'flip_y','yes').lower() == 'yes'
    arr = np.asarray(image, dtype=np.uint8)
    if flip:
        arr = np.ascontiguousarray(arr[::-1,:,:])
    scriptOp.copyNumpyArray(arr)
    return

def onGetCookLevel(scriptOp):
    return CookLevel.ALWAYS
