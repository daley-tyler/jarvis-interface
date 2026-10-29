"""JARVIS V1.6: interactive 3D world projection, identity-country linking.
Installed as a TouchDesigner Text DAT; uses existing normalized pinch coordinates.
No MediaPipe changes; lower-priority V1.4/V1.5 controllers are bypassed only
while an interaction starts on V1.6's globe/dock/country list/photo card.
"""
import math, json

W,H=960.,540.
BUTTON=(663.,75.,114.,35.)
ROWS=[(767.,201.+i*54.,183.,46.) for i in range(3)]
GLOBE_RADIUS=126.
_state={
    'open':False,'yaw':-28.,'pitch':-17.,'scale':1.0,
    'cx':556.,'cy':309.,'selected':None,
    'captured':None,'press_last':False,'pressed_at':0.,
    'start_p':(0.,0.),'start_yaw':0.,'start_pitch':0.,
    'start_center':(556.,309.),'start_dist':1.,'start_scale':1.,
    'armed_marker':None,'marker_pos':None,
    'target_yaw':None,'target_pitch':None,
    'stable_since':0.,'last_time':0.,'fresh_hand':False,
}
_CFG_TEXT=None
_CFG=None

def links():
    global _CFG_TEXT,_CFG
    h=op('/project1/gesture_hud')
    text=str(h.op('jv16_country_config').text)
    if _CFG is None or text != _CFG_TEXT:
        value=json.loads(text)
        cfg=value['links']
        if len(cfg)!=3:
            raise ValueError('Country configuration requires 3 links')
        for c in cfg:
            if not isinstance(c['country'],str):raise ValueError('Expected country string')
            lat=float(c['lat']);lon=float(c['lon'])
            if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid lat/lon')
        _CFG_TEXT=text;_CFG=cfg
    return _CFG

def inside(p,r):
    return r[0]<=p[0]<=r[0]+r[2] and r[1]<=p[1]<=r[1]+r[3]

def wrap(a):return (float(a)+180)%360-180

def _hand_pts(chop):
    try:return mod('/project1/gesture_hud/jv14_core_controller')._hands(chop)
    except Exception:return {}

def project(lat,lon):
    """Orthographic 3D globe projection with yaw and tilt; None on hidden hemisphere."""
    s=_state
    a=math.radians(float(lon));b=math.radians(float(lat))
    x=math.cos(b)*math.sin(a);y=math.sin(b);z=math.cos(b)*math.cos(a)
    t=math.radians(s['yaw']);c=math.cos(t);sine=math.sin(t)
    xx=c*x-sine*z;z1=sine*x+c*z
    t=math.radians(s['pitch']);cy=math.cos(t);sy=math.sin(t)
    yy=cy*y+sy*z1;vz=-sy*y+cy*z1
    if vz<0.07:return None
    r=GLOBE_RADIUS*_state['scale']
    return (_state['cx']+xx*r,_state['cy']-yy*r,vz)

def _marker_hit(p):
    for i,c in enumerate(links()):
        q=project(c['lat'],c['lon'])
        if q is not None and math.hypot(p[0]-q[0],p[1]-q[1])<=17:
            return i
    return None

def select(i):
    idx=int(i)
    if idx not in range(3):raise ValueError('Identity must be 0, 1, or 2')
    c=links()[idx]
    _state['selected']=idx
    _state['target_yaw']=wrap(c['lon'])
    _state['target_pitch']=max(-64.,min(64.,-float(c['lat'])))

def reset():
    _state.update(open=False,yaw=-28.,pitch=-17.,scale=1.,cx=556.,cy=309.,selected=None,
                  captured=None,press_last=False,target_yaw=None,target_pitch=None)

def _tick(dt):
    s=_state
    if not s['open'] or s['captured'] in ('spin','move','scale'):return
    if s['target_yaw'] is not None:
        diff=wrap(s['target_yaw']-s['yaw'])
        step=min(1.,max(.03,dt*6.))
        s['yaw']=wrap(s['yaw']+diff*step)
        s['pitch']+=(s['target_pitch']-s['pitch'])*step
        if abs(diff)<.15 and abs(s['target_pitch']-s['pitch'])<.15:
            s['target_yaw']=None;s['target_pitch']=None
    elif s['selected'] is None:
        s['yaw']=wrap(s['yaw']+dt*5.)

def _capture(kind,p,sec,chop):
    s=_state
    s['captured']=kind;s['pressed_at']=sec;s['start_p']=p
    s['start_yaw']=s['yaw'];s['start_pitch']=s['pitch']
    s['start_center']=(s['cx'],s['cy'])
    s['start_scale']=s['scale']
    s['start_dist']=None
    s['marker_pos']=p

def update(hud,chop,pointer,pressed,active,sec,panel_dragging,core_mode,workspace_capture):
    """Return True if V1.6 owns this gesture. Caller bypasses V1.5/V1.4.
    Uses the same callback pointer coordinate space (top-left, 960x540).
    """
    s=_state
    dt=max(0.,min(.08,sec-s['last_time'])) if s['last_time'] else 1./60.
    s['last_time']=sec
    _tick(dt)
    p=(max(0.,min(1.,float(pointer[0])))*W,
       max(0.,min(1.,float(pointer[1])))*H)
    if not active:
        s['captured']=None;s['press_last']=False
        return False
    if s['captured'] is not None:
        if not pressed:
            if s['captured']=='marker' and s['armed_marker'] is not None:
                # Short, stationary marker pinches activate on release.
                dx=p[0]-s['start_p'][0];dy=p[1]-s['start_p'][1]
                if dx*dx+dy*dy<14**2:
                    select(s['armed_marker'])
            s['captured']=None;s['armed_marker']=None;s['press_last']=False
            return False
        if s['captured']=='move':
            s['cx']=max(318.,min(664.,s['start_center'][0]+p[0]-s['start_p'][0]))
            s['cy']=max(245.,min(383.,s['start_center'][1]+p[1]-s['start_p'][1]))
        elif s['captured'] in ('spin','marker','scale'):
            hands=_hand_pts(chop)
            pinched=[v for v in hands.values() if v[2]]
            if len(pinched)>=2:
                a,b=pinched[:2]
                dist=max(25.,math.hypot(b[0]-a[0],b[1]-a[1]))
                if s['start_dist'] is None:
                    s['start_dist']=dist;s['start_scale']=s['scale']
                s['scale']=max(.50,min(1.26,s['start_scale']*dist/s['start_dist']))
                s['captured']='scale'
            else:
                if s['captured']=='scale':
                    s['captured']='spin';s['start_p']=p
                    s['start_yaw']=s['yaw'];s['start_pitch']=s['pitch']
                dx=p[0]-s['start_p'][0];dy=p[1]-s['start_p'][1]
                if s['captured']=='marker':
                    if dx*dx+dy*dy>16**2:
                        s['captured']='spin';s['armed_marker']=None
                    elif sec-s['pressed_at']>.20 and s['armed_marker'] is not None:
                        select(s['armed_marker'])
                        s['captured']='selected'  # prevent repeat on release
                if s['captured']=='spin':
                    s['target_yaw']=None;s['target_pitch']=None
                    s['selected']=None
                    s['yaw']=wrap(s['start_yaw']-(dx*.58))
                    s['pitch']=max(-64.,min(64.,s['start_pitch']-dy*.44))
        s['press_last']=True
        return True

    if not pressed:
        s['press_last']=False
        return False
    new=not s['press_last'];s['press_last']=True
    if not new:return False
    # Do not steal an existing legacy panel / V1.4 core / V1.5 workspace grab.
    if panel_dragging>=0 or core_mode not in (None,'idle') or workspace_capture is not None:
        return False
    if inside(p,BUTTON):
        s['open']=not s['open']
        s['captured']='button'
        if not s['open']:s['selected']=None
        return True
    if not s['open']:return False
    # Select via explicit country rows even if a marker is on the globe's far side.
    for i,rect in enumerate(ROWS):
        if inside(p,rect):
            select(i);_capture('row',p,sec,chop)
            return True
    if s['selected'] is not None and inside(p,(262.,224.,195.,195.)):
        # Consume card pinch while globe open; prevents unexpected legacy toggle.
        _capture('selected',p,sec,chop)
        return True
    r=GLOBE_RADIUS*s['scale']
    if inside(p,(s['cx']-r,s['cy']-r-26.,r*2.,28.)):
        _capture('move',p,sec,chop)
        return True
    if math.hypot(p[0]-s['cx'],p[1]-s['cy'])<=r+8:
        marker=_marker_hit(p)
        _capture('marker' if marker is not None else 'spin',p,sec,chop)
        s['armed_marker']=marker
        return True
    return False
