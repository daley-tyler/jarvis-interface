"""TouchDesigner V2.0 module: poll trusted local voice_command.json at most ten times per second.

Not installed into MediaPipe or gesture callbacks. Only allowlisted commands are
forwarded to the known V1.4/V1.5/V1.6 controllers and ambient audio component.
"""
import json
import os
import tempfile
import math
import time as _clock
from pathlib import Path

_ROOT = Path(project.folder).expanduser().resolve() / 'JARVIS_VOICE_V20'
_command = _ROOT / 'voice_command.json'
_status_file = _ROOT / 'voice_status.json'
_seq = None
_next_poll = 0.0
_last_status = ''
_last_action = 'No voice command received yet'
_last_error = ''
# Frame-driven, non-blocking country scan: no time.sleep() in TouchDesigner.
_SCAN_COUNTRIES = ('new_zealand', 'united_states', 'japan')
_scan = None
_scan_interval = 3.5  # seconds per country; configurable in settings.json


def _start_joey_scan():
    global _scan, _scan_interval
    h=op('/project1/gesture_hud')
    globe=mod(h.path+'/jv16_globe_controller')
    duration=(_json(_ROOT/'settings.json') or {}).get('joey_scan_seconds_per_country',3.5)
    try:duration=float(duration)
    except (TypeError,ValueError):duration=3.5
    _scan_interval=max(2.0,min(12.0,duration))
    # Country select() already animates yaw/pitch to the desired marker.
    globe._state['open']=True
    globe._state['captured']=None
    globe.select(0)
    _scan={'index':0,'next_at':_clock.monotonic()+_scan_interval}
    return 'Analyzing saved country links: New Zealand -> United States -> Japan'


def _tick_joey_scan():
    global _scan, _last_action
    if _scan is None:return
    h=op('/project1/gesture_hud')
    if h is None:
        _scan=None
        return
    try:
        globe=mod(h.path+'/jv16_globe_controller')
        st=globe._state
        # If the person interacts with the globe or changes a selection,
        # do not fight their hand gestures: stop the automatic tour.
        if not st.get('open') or st.get('captured') is not None or st.get('selected')!=_scan['index']:
            _last_action='Joey locations scan interrupted by manual globe interaction'
            _scan=None
            return
        if _clock.monotonic()<_scan['next_at']:return
        idx=_scan['index']+1
        if idx>=len(_SCAN_COUNTRIES):
            # Leave the final country selection open after the tour.
            _last_action='Joey locations scan complete - Japan selected'
            _scan=None
            return
        globe.select(idx)
        _scan['index']=idx
        _scan['next_at']=_clock.monotonic()+_scan_interval
        _last_action='Joey scan: '+_SCAN_COUNTRIES[idx].replace('_',' ')
    except Exception as exc:
        _scan=None
        _last_action='Saved country tour stopped'
        print('JARVIS tour error:',type(exc).__name__)


def _json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None


def _fresh(packet, timestamp, age):
    try:
        stamp = float(packet.get(timestamp, 0))
        delta = _clock.time() - stamp
        return math.isfinite(stamp) and -2 <= delta <= age
    except (TypeError, ValueError, AttributeError):
        return False


def _ack(seq, ok, error=''):
    fd, temp = tempfile.mkstemp(prefix='ack_', dir=str(_ROOT))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump({'seq': seq, 'ok': ok, 'error': error, 'at': _clock.time()}, out)
        os.replace(temp, _ROOT / 'voice_ack.json')
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def _dispatch(name,arg):
    global _scan
    # Any new explicit voice action stops a running scan. Reissuing the scan
    # starts again from New Zealand.
    _scan=None
    if name=='joey_scan':
        if arg!='start':raise ValueError('Invalid Joey scan action')
        return _start_joey_scan()
    h=op('/project1/gesture_hud')
    if not h:raise RuntimeError('JARVIS gesture_hud component is missing')
    if name=='country':
        i={'new_zealand':0,'united_states':1,'japan':2}[arg]
        ctl=mod(h.path+'/jv16_globe_controller')
        ctl._state['open']=True
        ctl.select(i)
        return 'Globe country selected: '+arg
    if name=='globe':
        ctl=mod(h.path+'/jv16_globe_controller')
        if arg=='reset':ctl.reset()
        elif arg in ('open','close'):
            ctl._state['open']=(arg=='open')
            if arg=='close':ctl._state['selected']=None
        else:raise ValueError('Invalid globe action')
        return 'Globe '+arg
    if name=='workspace':
        ctl=mod(h.path+'/jv15_workspace_controller')
        if arg=='close':ctl._state['open']=None;ctl._state['captured']=None
        elif arg in ('system','tracking','commands'):ctl.show(arg)
        else:raise ValueError('Invalid workspace')
        return 'Workspace '+arg
    if name=='background':
        if arg not in ('camera','cinematic'):raise ValueError('Invalid mode')
        h.op('background_mode').par.index=0 if arg=='camera' else 1
        return 'Background '+arg
    if name=='core':
        if arg!='reset':raise ValueError('Invalid core action')
        mod(h.path+'/jv14_core_controller').reset()
        return 'Central hologram reset'
    if name=='identity':
        if arg!='close':raise ValueError('Invalid identity action')
        mod(h.path+'/jv16_globe_controller')._state['selected']=None
        return 'Globe identity closed'
    if name=='ambience':
        if arg not in ('mute','unmute'):raise ValueError('Invalid ambience')
        a=h.op('jarvis_ambience')
        if not a:raise RuntimeError('Ambient audio is not installed')
        a.par.Mute=1 if arg=='mute' else 0
        return 'Ambience '+arg
    raise ValueError('Unknown voice action: '+str(name))


def poll(frame):
    global _seq,_last_status,_last_action,_last_error,_next_poll
    now = _clock.monotonic()
    if now < _next_poll:
        return
    _next_poll = now + 0.1
    s=_json(_status_file)
    if not isinstance(s, dict) or not _fresh(s, 'updated_at', 30):
        s={}
    h=op('/project1/gesture_hud')
    if not h:return
    ambience=h.op('jarvis_ambience')
    if ambience:
        # V1.6.4 auto-ducking: speaking OR listening lowers the loop.
        talking=bool(s.get('speaking',False) or s.get('listening',False))
        try:
            if bool(ambience.par.Voiceactive.eval())!=talking:
                ambience.par.Voiceactive=int(talking)
        except Exception:pass
    cmd=_json(_command)
    if isinstance(cmd,dict):
        try:n=int(cmd.get('seq',0))
        except (ValueError,TypeError,OverflowError):n=0
        if _seq is None:
            # Initial attach deliberately ignores a previous-session command.
            _seq=n
        elif n>_seq:
            _seq=n
            try:
                if not _fresh(cmd, 'at', 15):
                    raise ValueError('Expired or invalid voice command')
                _last_action=_dispatch(str(cmd.get('command','')),str(cmd.get('argument','')))
                _last_error=''
                _ack(n, True)
            except Exception as exc:
                _last_error='scene_action_failed'
                _last_action='Action rejected'
                print('JARVIS command rejected:',type(exc).__name__)
                try:
                    _ack(n, False, 'scene_action_failed')
                except OSError:
                    pass
    else:
        if _seq is None:_seq=0
    # Advance after dispatch; this is called from TouchDesigner's Execute DAT
    # at a bounded rate, without pausing or blocking the HUD timeline.
    _tick_joey_scan()
    visible=json.dumps({'phase':s.get('phase','waiting'),
                        'last_action':_last_action,
                        'error_code':_last_error or ('voice_error' if s.get('error_code') else '')},indent=2)
    if visible!=_last_status:
        status_node=h.op('jv20_voice_status')
        if status_node:status_node.text=visible
        _last_status=visible
