"""JARVIS V2.0 voice service for macOS.

Local: push-to-talk microphone -> faster-whisper -> allowlisted actions -> macOS say.
Uses files beside this script to communicate with an installed TouchDesigner bridge.
No speech transcript is persisted or forwarded to another service.
Microphone capture requires an explicit owner opt-in.
"""
import argparse
from contextlib import contextmanager
import math
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from command_router import route

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / 'settings.json'
COMMAND_FILE = ROOT / 'voice_command.json'
STATUS_FILE = ROOT / 'voice_status.json'
ACK_FILE = ROOT / 'voice_ack.json'
ACTIONS = {
    'country': {'new_zealand', 'united_states', 'japan'},
    'globe': {'open', 'close', 'reset'},
    'workspace': {'system', 'tracking', 'commands', 'close'},
    'background': {'camera', 'cinematic'}, 'core': {'reset'},
    'identity': {'close'}, 'ambience': {'mute', 'unmute'},
    'joey_scan': {'start'},
}
PHASES = {'idle', 'listening', 'transcribing', 'speaking', 'error', 'waiting'}


def read_json(path, fallback):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else fallback
    except (FileNotFoundError, ValueError, OSError):
        return fallback


def atomic_json(path, obj):
    # Works even while TouchDesigner reads a previous version of the JSON file.
    fd, temp = tempfile.mkstemp(prefix='jarvis_', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(obj, out, indent=2, ensure_ascii=True)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def status(phase='idle', text='', response='', error=''):
    # The compatibility arguments are deliberately discarded, including errors
    # that could contain a transcript or a personal filesystem path.
    phase = phase if phase in PHASES else 'error'
    atomic_json(STATUS_FILE, {'phase': phase,
                             'listening': phase in ('listening', 'transcribing'),
                             'speaking': phase == 'speaking',
                             'error_code': 'voice_error' if error else '',
                             'updated_at': time.time()})


def emit(command, argument, spoken):
    if command not in ACTIONS or argument not in ACTIONS[command]:
        raise ValueError('Only canonical scene actions can be persisted.')
    old=read_json(COMMAND_FILE, {})
    try:
        previous = int(old.get('seq', 0))
    except (TypeError, ValueError, OverflowError):
        previous = 0
    seq=max(previous + 1, time.time_ns())
    packet={'seq':seq,'command':command,'argument':argument,'at':time.time()}
    atomic_json(COMMAND_FILE,packet)
    return packet


def ollama_response(text, config):
    # Kept as an inert compatibility hook. Raw speech never leaves this process,
    # even if an older settings file enables Ollama.
    return None


def say(text, config):
    voice=str(config.get('voice','Daniel')).strip() or 'Daniel'
    rate=max(105,min(220,int(config.get('speech_rate',145))))
    if sys.platform!='darwin':
        print('VOICE (macOS say unavailable on this machine):',text)
        return
    command=['say','-v',voice,'-r',str(rate),text]
    try:
        subprocess.run(command,check=True,timeout=30)
    except (subprocess.CalledProcessError,FileNotFoundError,subprocess.TimeoutExpired):
        print('Preferred voice unavailable; trying macOS default voice.')
        try:subprocess.run(['say','-r',str(rate),text],check=True,timeout=30)
        except Exception as exc:print('Voice playback failed:',type(exc).__name__)


def handle(text,config,no_speak=False):
    result=route(text)
    response=result.response
    if result.command=='unknown':
        ai=ollama_response(text,config)
        if ai:response=ai
    # Never forward unknown/free-form text to TouchDesigner.
    if result.command not in ('none','unknown'):
        packet=emit(result.command,result.argument,text)
        print('QUEUED FOR TOUCHDESIGNER:', packet['command'], packet['argument'])
        ack = wait_for_ack(packet['seq'], config.get('ack_timeout', 2.0))
        if ack is None:
            response = 'Command queued. TouchDesigner has not confirmed this action.'
        elif not ack.get('ok'):
            response = 'TouchDesigner could not complete the action. Check the scene controllers.'
    else:
        print('NO ACTION:',result.command)
    status('idle',text,response)
    print('JARVIS:',response)
    if not no_speak:
        status('speaking',text,response)
        try:say(response,config)
        finally:status('idle',text,response)
    return result


def wait_for_ack(seq, timeout):
    deadline = time.monotonic() + max(0.0, min(5.0, float(timeout)))
    while True:
        ack = read_json(ACK_FILE, {})
        if ack.get('seq') == seq:
            return ack
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.025)


@contextmanager
def service_lock():
    # All entry points share one writer. The OS releases the lock after a crash.
    import fcntl
    with (ROOT / 'voice_service.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another JARVIS voice service is already running.') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def record(seconds, stop=None, device=None, microphone_allowed=False):
    if not microphone_allowed:
        raise RuntimeError('Microphone capture is disabled until the owner explicitly opts in.')
    # Blocking reads run only in the voice process, never in TouchDesigner.
    import sounddevice as sd
    import numpy as np
    blocks = []
    with sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                        device=device, blocksize=1600) as stream:
        for _ in range(max(1, math.ceil(seconds * 10))):
            if stop is not None and stop.is_set():
                break
            block, overflow = stream.read(1600)
            if overflow:
                raise RuntimeError('Microphone overflow; please retry with less system load.')
            blocks.append(block[:, 0].copy())
    return np.concatenate(blocks) if blocks else np.empty(0, dtype=np.float32)


def transcribe(model,audio):
    if len(audio) < 1600:
        return ''
    segments,_=model.transcribe(audio,language='en',beam_size=1,
                                vad_filter=True,condition_on_previous_text=False)
    return ' '.join(seg.text.strip() for seg in segments).strip()


def _main(argv=None):
    ap=argparse.ArgumentParser(description='JARVIS voice bridge (macOS)')
    ap.add_argument('--text',help='Send one typed command; no microphone/model needed')
    ap.add_argument('--no-speak',action='store_true',help='Do not use macOS say')
    ap.add_argument('--activation', choices=('panel', 'enter'), default='panel')
    ap.add_argument('--list-devices', action='store_true')
    ap.add_argument('--enable-microphone', action='store_true',
                    help='Owner opt-in for capture on an explicit Speak/Enter action')
    ap.add_argument('--local-model-only', action='store_true', help='Never download model files')
    args=ap.parse_args(argv)
    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return 0
    config=read_json(SETTINGS,{})
    if not config:
        print('Missing settings.json. Re-extract/install the complete package.',file=sys.stderr)
        return 2
    try:
        config['record_seconds'] = float(config.get('record_seconds', 5))
        config['ack_timeout'] = float(config.get('ack_timeout', 2))
        if not (2 <= config['record_seconds'] <= 12 and 0 <= config['ack_timeout'] <= 5):
            raise ValueError('capture must be 2–12 seconds and acknowledgement timeout 0–5 seconds')
    except (TypeError, ValueError) as exc:
        print('Invalid voice settings:', type(exc).__name__, file=sys.stderr)
        return 2
    if args.text is not None:
        handle(args.text,config,args.no_speak)
        return 0
    if not args.enable_microphone:
        print('Microphone capture is disabled. Use --text for a camera-free, audio-free test.', file=sys.stderr)
        return 2
    config['microphone_enabled'] = True
    try:
        from faster_whisper import WhisperModel
        import sounddevice as sd
    except ImportError:
        print('Dependencies missing. Run START_JARVIS_VOICE.command first.',file=sys.stderr)
        return 2
    print('Loading Whisper model (first use downloads it once)...')
    try:
        model=WhisperModel(config.get('whisper_model','tiny.en'),device='cpu',
                           compute_type='int8',cpu_threads=2,
                           local_files_only=args.local_model_only)
    except Exception as exc:
        print('Speech model failed to load:',type(exc).__name__,file=sys.stderr)
        return 2
    if args.activation == 'panel':
        from voice_panel import run_panel
        run_panel(model, config, sys.modules[__name__], args.no_speak)
        return 0
    print('\nJARVIS V2.0 READY: press Enter to record, or type q then Enter to quit.')
    print('Try: "Jarvis, analyze Joey locations"; "Jarvis, show Japan"; "Jarvis, open tracking".')
    print('Ambient sound is automatically lowered while listening or speaking.\n')
    status('idle')
    seconds=max(2,min(12,float(config.get('record_seconds',5))))
    while True:
        try:
            line=input('Press ENTER to speak (q to quit)> ').strip()
            if line.lower() in ('q','quit','exit'):break
            if line.startswith('/text '):
                handle(line[6:],config,args.no_speak);continue
            print('Listening for %.1f seconds...' % seconds,flush=True)
            status('listening')
            try:
                samples=record(seconds, device=config.get('input_device'), microphone_allowed=True)
            except Exception as exc:
                status('error',error=str(exc))
                print('Microphone error:',type(exc).__name__)
                print('Allow Terminal microphone access in System Settings -> Privacy & Security -> Microphone.')
                continue
            status('transcribing')
            try:
                words=transcribe(model,samples)
            finally:
                del samples
            print('Recognition completed; transcript discarded after routing.')
            if words:handle(words,config,args.no_speak)
            else:status('idle')
            del words
        except (KeyboardInterrupt,EOFError):
            break
        except Exception as exc:
            print('Voice command failed:',type(exc).__name__)
            status('error',error=str(exc))
    status('idle')
    print('JARVIS voice service stopped.')
    return 0

def main(argv=None):
    try:
        with service_lock():
            try:
                return _main(argv)
            finally:
                status('idle')
    except (RuntimeError, OSError) as exc:
        print('Voice service error:', type(exc).__name__, file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
