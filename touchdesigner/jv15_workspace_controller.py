"""JARVIS V1.5 local interactive workspaces. TouchDesigner Text DAT module.

Uses EXISTING render callback's corrected (x, 1-y) cursor, never alters
MediaPipe and does not read webcam pixels. Coordinates are 960 x 540.
"""

W, H = 960., 540.
DOCK = (310., 68., 340., 51.)
BUTTONS = [(318.,76.,105.,34.), (428.,76.,105.,34.), (538.,76.,105.,34.)]
WINDOW_W, WINDOW_H = 388., 263.
INITIAL_X, INITIAL_Y = 286., 147.
MODES = ('system', 'tracking', 'commands')

_state = {
    'open': None,
    'x': INITIAL_X, 'y': INITIAL_Y,
    'captured': None,  # dock / panel / drag
    'drag_start': (0.,0.), 'window_start': (INITIAL_X,INITIAL_Y),
    'pressed_last': False, 'pointer': (480.,270.),
    'hands': {}, 'tracking': False,
}


def _inside(p, r):
    x,y = p; a,b,w,h = r
    return a <= x <= a+w and b <= y <= b+h


def _identity_hit(point, shown, offsets, rects):
    if not shown: return False
    for i,(x,y,w,h) in enumerate(rects):
        try: ox,oy = offsets[i]
        except Exception: ox,oy = (0.,0.)
        if _inside(point,(x+ox,y+oy,w,h)):
            return True
    return False


def _hands(chop):
    # Use precisely the SAME channels and vertical flip as working V1.4.
    try:
        return mod('/project1/gesture_hud/jv14_core_controller')._hands(chop)
    except Exception:
        return {}


def update(hud, chop, pointer, pressed, active, panel_dragging,
           panels_shown, panel_offsets, panel_rects, core_mode):
    """Return True while this UI owns pinch. Render callbacks will then
    suppress core/card pinch for that frame but continue all tracking.
    """
    s=_state
    p=(max(0.,min(1.,float(pointer[0])))*W,
       max(0.,min(1.,float(pointer[1])))*H)
    s['pointer']=p
    s['tracking']=bool(active)
    s['hands']=_hands(chop) if active else {}
    if not active:
        s['captured']=None
        s['pressed_last']=False
        return False

    if s['captured'] is not None:
        if not pressed:
            s['captured']=None
            s['pressed_last']=False
            return False
        if s['captured']=='drag':
            x0,y0=s['drag_start']; wx,wy=s['window_start']
            s['x']=max(18.,min(W-WINDOW_W-18.,wx+(p[0]-x0)))
            s['y']=max(125.,min(H-WINDOW_H-14.,wy+(p[1]-y0)))
        s['pressed_last']=True
        return True

    # If a hand began pinching elsewhere, don't steal it while moving across UI.
    if not pressed:
        s['pressed_last']=False
        return False
    new_press=not s['pressed_last']
    s['pressed_last']=True
    if not new_press:
        return False

    # Preserve ownership of an existing V1.4 core grab or identity card drag.
    if panel_dragging>=0 or core_mode not in ('idle',None):
        return False
    # Existing identity cards have priority where they overlap our UI.
    if _identity_hit(p,panels_shown,panel_offsets,panel_rects):
        return False

    # Dock is first-class UI control; always reachable above windows.
    for i,rect in enumerate(BUTTONS):
        if _inside(p,rect):
            target=MODES[i]
            s['open']=None if s['open']==target else target
            s['captured']='dock'
            return True

    if s['open'] is not None:
        rect=(s['x'],s['y'],WINDOW_W,WINDOW_H)
        if _inside(p,rect):
            # Close button is an intentional interaction, NOT drag.
            if _inside(p,(s['x']+349.,s['y']+13.,24.,18.)):
                s['open']=None
                s['captured']='panel'
                return True
            if _inside(p,(s['x'],s['y'],WINDOW_W,41.)):
                s['captured']='drag'
                s['drag_start']=p
                s['window_start']=(s['x'],s['y'])
            else:
                s['captured']='panel'  # consume non-action body pinches
            return True
    return False


def show(mode):
    """Manual tests from Textport: mod('/.../jv15_workspace_controller').show('system')"""
    m=str(mode).lower().strip()
    if m not in MODES:
        raise ValueError('Expected system, tracking or commands')
    _state['open']=m
    _state['captured']=None
    _state['pressed_last']=False


def reset():
    _state.update(open=None,x=INITIAL_X,y=INITIAL_Y,captured=None,
                  drag_start=(0.,0.),window_start=(INITIAL_X,INITIAL_Y),
                  pressed_last=False)
