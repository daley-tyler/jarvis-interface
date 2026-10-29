"""JARVIS V1.6 software 3D holographic globe drawn into existing HUD RGBA.
An actual perspective-correct (orthographic) spherical projection of world texture,
with yaw/pitch controlled by MediaPipe gestures. Requires NumPy only at runtime.
"""
import math,json
from pathlib import Path
import numpy as np
from functools import lru_cache

_CACHE={}
_FRAMES={}
_XY=None

def _asset(name):
    h=op('/project1/gesture_hud')
    cfg=json.loads(str(h.op('jv16_install_state').text))
    path=str(Path(cfg['assets_dir'])/(name+'.npy'))
    if path not in _CACHE:_CACHE[path]=np.load(path,allow_pickle=False)
    return _CACHE[path]

def _sprite(image,sprite,x,y):
    # Use the exactly tested V1.5 alpha compositor.
    mod('/project1/gesture_hud/jv15_workspace_draw')._blend(image,sprite,x,y)

def _write(image,txt,x,y,palette=0):
    mod('/project1/gesture_hud/jv15_workspace_draw')._write(image,txt,x,y,palette)

def _photo(idx):
    h=op('/project1/gesture_hud')
    source=Path(str(h.op('settings')['assets_dir',1].val))/'runtime'/('panel_'+str(idx)+'.npy')
    key=str(source)
    if key not in _CACHE:
        a=np.load(key,allow_pickle=False)
        if a.shape!=(190,192,4):raise RuntimeError('Expected existing V1.3 portrait panel size: '+key)
        _CACHE[key]=a
    return _CACHE[key]

def _sphere(yaw,pitch,scale):
    # Cache approximately every 0.7 degree or 0.02 scale. CPU-friendly even on M2 Air.
    key=(int(round(yaw/.7)),int(round(pitch/.7)),int(round(scale/.02)))
    if key in _FRAMES:return _FRAMES[key]
    if len(_FRAMES)>=10:_FRAMES.clear()
    yaw=math.radians(key[0]*.7);pitch=math.radians(key[1]*.7)
    scale=key[2]*.02
    D=340
    y,x=np.ogrid[:D,:D]
    X=np.broadcast_to((x-(D-1)/2.)/(126.*scale),(D,D)).astype(np.float32)
    Y=np.broadcast_to(((D-1)/2.-y)/(126.*scale),(D,D)).astype(np.float32)
    rr=X*X+Y*Y
    inside=rr<=1.
    Z=np.sqrt(np.maximum(0.,1.-rr))
    # Inverse yaw/pitch rotation to sample latitude and longitude on sphere.
    a=np.cos(yaw);b=np.sin(yaw);c=np.cos(pitch);d=np.sin(pitch)
    v=d*Y+c*Z
    world_y=c*Y-d*Z
    world_x=a*X+b*v
    world_z=-b*X+a*v
    lon=np.arctan2(world_x,world_z)
    lat=np.arcsin(np.clip(world_y,-1.,1.))
    tex=_asset('world_texture')
    tx=np.mod(((lon+np.pi)/(2*np.pi)*tex.shape[1]).astype(np.int32),tex.shape[1])
    ty=np.clip(((np.pi/2-lat)/np.pi*(tex.shape[0]-1)).astype(np.int32),0,tex.shape[0]-1)
    sample=tex[ty,tx]
    rim=np.clip(1.-np.sqrt(np.maximum(0.,1.-rr)),0.,1.)
    light=np.clip(.35+.58*(.45*X+.29*Y+.82*Z),.42,1.10)
    rgb=sample.astype(np.float32)*light[:,:,None]
    # Glow of atmospheric cyan rim, extra bright at edge.
    rgb[:,:,0]+=5+8*rim
    rgb[:,:,1]+=15+22*rim
    rgb[:,:,2]+=20+30*rim
    outer=(rr>.965)&inside
    rgb[:,:,0][outer]=48
    rgb[:,:,1][outer]=197
    rgb[:,:,2][outer]=224
    alpha=np.where(inside,210+44*rim,0).astype(np.uint8)
    out=np.empty((D,D,4),dtype=np.uint8)
    out[:,:,:3]=np.uint8(np.clip(rgb,0,255))
    out[:,:,3]=alpha
    _FRAMES[key]=out
    return out

def _line(image,x0,y0,x1,y1):
    x0=int(x0);y0=int(y0);x1=int(x1);y1=int(y1)
    n=max(2,int(math.hypot(x1-x0,y1-y0)))
    xs=np.rint(np.linspace(x0,x1,n)).astype(np.int32)
    ys=np.rint(np.linspace(y0,y1,n)).astype(np.int32)
    inside=(xs>=0)&(xs<image.shape[1])&(ys>=0)&(ys<image.shape[0])
    xs=xs[inside];ys=ys[inside]
    image[ys,xs,:]=np.array([28,182,213,225],dtype=np.uint8)

def draw(image,t=0.):
    c=mod('/project1/gesture_hud/jv16_globe_controller')
    s=c._state
    # Launcher always visible; no other V1.5 dock changes.
    _sprite(image,_asset('button_on' if s['open'] else 'button_off'),663,74)
    _write(image,'GLOBE',687,86,1 if s['open'] else 0)
    if not s['open']:return
    _write(image,'GEOSPATIAL / IDENTITY LINKS',475,149,1)
    # Drag handle + projected textured sphere.
    _sprite(image,_asset('globe_header'),int(s['cx']-133),int(s['cy']-126*s['scale']-31))
    _write(image,'HOLD + DRAG TO MOVE',int(s['cx']-111),int(s['cy']-126*s['scale']-24),0)
    globe=_sphere(s['yaw'],s['pitch'],s['scale'])
    _sprite(image,globe,int(s['cx']-170),int(s['cy']-170))
    links=c.links()
    for i,item in enumerate(links):
        p=c.project(item['lat'],item['lon'])
        if p is None:continue
        target=bool(s['selected']==i)
        _sprite(image,_asset('marker_selected' if target else 'marker'),p[0]-10,p[1]-10)
        _write(image,str(i+1),p[0]-4,p[1]-6,1)
    # Country list always accessible, even when a location rotates behind Earth.
    _write(image,'COUNTRY TARGETS',770,173,1)
    for i,info in enumerate(links):
        x,y,w,h=c.ROWS[i]
        active=s['selected']==i
        _sprite(image,_asset('row_on' if active else 'row_off'),x,y)
        _write(image,'ID '+str(i+1)+' / '+str(info['country'])[:13],x+7,y+8,1 if active else 0)
        _write(image,'PINCH TO LOCATE',x+7,y+27,0)
    if s['selected'] is not None:
        k=int(s['selected'])
        point=c.project(links[k]['lat'],links[k]['lon'])
        if point is not None:
            _line(image,455,309,point[0],point[1])
        _write(image,'SELECTED / '+str(links[k]['country'])[:14],266,203,1)
        _sprite(image,_photo(k),263,224)
        _write(image,'COUNTRY LINK / ID '+str(k+1),264,423,0)
    else:
        _write(image,'PINCH MARKER OR COUNTRY ROW',260,442,0)
    _write(image,'DRAG GLOBE TO ROTATE / TWO HANDS TO ZOOM',481,489,0)
