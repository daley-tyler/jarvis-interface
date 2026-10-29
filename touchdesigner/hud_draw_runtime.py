"""TouchDesigner HUD renderer: NumPy ONLY (no Pillow/PIL needed).

Uses external pre-rendered .npy RGBA graphics. Motion, tracking, panel dragging,
alpha fading, and live compositing remain interactive in TouchDesigner.
Those sprites and their design-time generator are excluded from this
source-only checkout. See docs/DISTRIBUTION.md for the packaging decision.
"""
import math
from pathlib import Path
import numpy as np

W, H = 960, 540
PANELS = [(40, 172, 192, 190), (728, 111, 192, 190), (728, 318, 192, 190)]
_CACHE = {}


def _asset(assets_dir, name):
    file = str(Path(assets_dir).expanduser() / 'runtime' / (name + '.npy'))
    if file not in _CACHE:
        image = np.load(file, allow_pickle=False)
        if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
            raise ValueError('Invalid sprite: ' + file)
        _CACHE[file] = image
    return _CACHE[file]


def _draw(base, sprite, x, y, opacity=1.0, scale=1.0):
    """Straight-alpha RGBA over, clipped to image bounds."""
    if opacity < .006 or scale < .05:
        return
    if scale != 1.0:
        sw, sh = max(1, int(sprite.shape[1]*scale)), max(1, int(sprite.shape[0]*scale))
        # Fast nearest-neighbor scaling avoids external image libraries.
        iy = np.minimum((np.arange(sh)/scale).astype(np.intp),sprite.shape[0]-1)
        ix = np.minimum((np.arange(sw)/scale).astype(np.intp),sprite.shape[1]-1)
        sprite = sprite[iy[:,None],ix[None,:]]
    x, y = int(x), int(y)
    sh, sw = sprite.shape[:2]
    bx0, by0 = max(0,x), max(0,y)
    bx1, by1 = min(W,x+sw), min(H,y+sh)
    if bx0 >= bx1 or by0 >= by1:
        return
    sub = sprite[by0-y:by1-y,bx0-x:bx1-x]
    # Early exit for fully transparent tile.
    if not np.any(sub[:,:,3]):
        return
    dest = base[by0:by1,bx0:bx1]
    alpha = (sub[:,:,3:4].astype(np.float32)/255.0) * opacity
    dst_alpha = dest[:,:,3:4].astype(np.float32)/255.0
    out_alpha = alpha + dst_alpha*(1.0-alpha)
    # Straight (non-premultiplied) alpha, required by Over TOP.
    colors = (sub[:,:,:3].astype(np.float32)*alpha +
              dest[:,:,:3].astype(np.float32)*dst_alpha*(1.0-alpha))
    rgb = colors / np.maximum(out_alpha, 0.00001)
    dest[:,:,:3] = np.clip(rgb,0,255).astype(np.uint8)
    dest[:,:,3:4] = np.clip(out_alpha*255,0,255).astype(np.uint8)


def render(t=0.0, asset_dir='', pointer=(0.46,0.42), visible=1.0,
           panel_offsets=None, tracking=False, grabbed=-1, face=(0.5,0.5)):
    """Return a mutable transparent RGBA NumPy array (540,960,4), uint8."""
    image = _asset(asset_dir,'base').copy()
    # Animated vertical scanner bar.
    line = int((t*55)%H)
    image[line:line+2,:,1] = np.maximum(image[line:line+2,:,1],70)
    image[line:line+2,:,3] = np.maximum(image[line:line+2,:,3],22)

    # Wire face head follows a tracked face (if a compatible coordinate CHOP exists).
    fi = int((t*.55/(2*math.pi)*24)%24)
    cx = 852 + (face[0]-.5)*55
    cy = 281 + (face[1]-.5)*30
    sprite = _asset(asset_dir, 'face_%02d'%fi)
    _draw(image, sprite, cx-sprite.shape[1]/2, cy-sprite.shape[0]/2)

    # Pinch panels fade + scale in one by one, then move with hand.
    offsets = panel_offsets or [(0,0),(0,0),(0,0)]
    if visible > .012:
        for i,(x,y,w,h) in enumerate(PANELS):
            v = max(0.0,min(1.0,visible*1.35-i*.10))
            if v < .025:
                continue
            image_panel = _asset(asset_dir,'panel_%d%s'%(i,'_focus' if grabbed == i else ''))
            ox, oy = offsets[i]
            _draw(image,image_panel,x+ox+(1-v)*12,y+oy+(1-v)*35,
                  opacity=min(1.0,visible*1.25),scale=v)

    # V1.6.3 globe and country-linked identity overlay.
    mod('/project1/gesture_hud/jv16_globe_draw').draw(image=image,t=t)

    # Draw interactive floating workspaces AFTER identity cards but BEFORE cursor.
    # New module uses NumPy RGBA; no extra runtime dependencies.
    mod('/project1/gesture_hud/jv15_workspace_draw').draw(
        image=image, t=t, pointer=pointer, tracking=tracking)

    status = 'status_open' if visible>.65 else ('status_scanning' if visible<.15 else 'status_reconstructing')
    _draw(image,_asset(asset_dir,status),24,77)

    px = int(max(0.0,min(1.0,pointer[0]))*W)
    py = int(max(0.0,min(1.0,pointer[1]))*H)
    _draw(image,_asset(asset_dir,'cursor_'+str(int(math.sin(5*t)>0))),px-32,py-32)
    _draw(image,_asset(asset_dir,'track_on' if tracking else 'track_demo'),
          min(W-145,px+28), max(61,py-25))
    return image
