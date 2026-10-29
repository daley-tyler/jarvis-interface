"""JARVIS V1.5 workspace draw. Uses ONLY numpy and saved .npy sprites.

Overlay is rendered into existing transparent HUD BEFORE original cursor,
not as a full-screen extra TOP. No Pillow install is required on the Mac.
"""
import numpy as np
from pathlib import Path
import json

_CACHE={}
_TEXT_KEY=None
_TEXT_LAYER=None


def _asset(name):
    h=op('/project1/gesture_hud')
    cfg=json.loads(str(h.op('jv15_install_state').text))
    path=str(Path(cfg['assets_dir'])/(name+'.npy'))
    if path not in _CACHE:
        _CACHE[path]=np.load(path,allow_pickle=False)
    return _CACHE[path]


def _blend(base, sprite, x, y):
    """Straight-alpha sprite composite into arbitrary sized RGBA uint8 array."""
    x,y=int(round(x)),int(round(y))
    H,W=base.shape[:2]; h,w=sprite.shape[:2]
    x0,y0=max(0,x),max(0,y);x1,y1=min(W,x+w),min(H,y+h)
    if x1<=x0 or y1<=y0:return
    src=sprite[y0-y:y1-y,x0-x:x1-x]
    dest=base[y0:y1,x0:x1]
    sa=src[:,:,3:4].astype(np.float32)/255.
    if not np.any(sa):return
    da=dest[:,:,3:4].astype(np.float32)/255.
    oa=sa+da*(1.-sa)
    color=src[:,:,:3].astype(np.float32)*sa + dest[:,:,:3].astype(np.float32)*da*(1.-sa)
    dest[:,:,:3]=np.clip(color/np.maximum(oa,.0001),0,255).astype(np.uint8)
    dest[:,:,3:4]=np.clip(oa*255,0,255).astype(np.uint8)


def _write(canvas, text, x, y, palette=0):
    atlas=_asset('glyphs')
    x=int(x);y=int(y)
    for c in str(text).upper()[:45]:
        code=ord(c)
        if 32<=code<127:
            _blend(canvas,atlas[int(palette),code-32],x,y)
        x+=9


def _tracker_row(hands,key):
    if key not in hands:return 'NOT SEEN'
    x,y,pinch=hands[key]
    return '{:3.0f},{:3.0f}  {}'.format(x,y,'PINCH' if pinch else 'OPEN')


def _dynamic(state, t):
    global _TEXT_KEY,_TEXT_LAYER
    hud=op('/project1/gesture_hud')
    core_mod=mod(hud.path+'/jv14_core_controller')
    core=core_mod._state
    bg=hud.op('background_mode')
    try: camera=(int(bg.par.index.eval())==0)
    except Exception:camera=True
    cb=mod(hud.path+'/render_callbacks')
    cbstate=cb._state
    mode=state['open']
    if mode=='system':
        values=(('CAMERA' if camera else 'CINEMATIC'),
                'ACTIVE' if state['tracking'] else 'NO HAND',
                'VISIBLE' if cbstate.get('shown',False) else 'HIDDEN',
                '{:.2f} X'.format(core['scale']),
                '{:+.1f} DEG'.format(core['rotation']))
        palette=(0,1,1,0,0)
    elif mode=='tracking':
        hands=state['hands']
        ptr=state['pointer']
        values=(_tracker_row(hands,'h1'),_tracker_row(hands,'h2'),
                '{:3.0f},{:3.0f}'.format(*ptr),
                ('H1 {} / H2 {}'.format('YES' if hands.get('h1',(0,0,False))[2] else 'NO',
                                       'YES' if hands.get('h2',(0,0,False))[2] else 'NO')),
                str(len(hands)))
        palette=(0,0,1,1,0)
    else:
        values=None
        palette=None
    key=(mode,values,tuple(palette or ()))
    if key==_TEXT_KEY and _TEXT_LAYER is not None:
        return _TEXT_LAYER
    layer=np.zeros((263,388,4),dtype=np.uint8)
    if values:
        # Blank areas to right of labels are reserved by the static art.
        for i,v in enumerate(values):
            _write(layer,v,225,75+i*31,palette=palette[i])
    _TEXT_KEY=key;_TEXT_LAYER=layer
    return layer


def draw(image, t=0., pointer=(.5,.5), tracking=False):
    ctl=mod('/project1/gesture_hud/jv15_workspace_controller')
    state=ctl._state
    active=state['open']
    selected={'system':1,'tracking':2,'commands':3}.get(active,0)
    _blend(image,_asset('dock_'+str(selected)),310,68)
    if active:
        x,y=state['x'],state['y']
        _blend(image,_asset('panel_'+active),x,y)
        if active!='commands':
            _blend(image,_dynamic(state,t),x,y)
