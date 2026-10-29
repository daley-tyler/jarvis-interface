"""Deterministic, complete-phrase commands. No scene or speech dependencies."""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    command: str
    argument: str
    response: str


def route(spoken: str) -> Result:
    if not isinstance(spoken, str) or len(spoken) > 1000:
        return Result('none', '', 'Please use a short JARVIS command.')
    q = re.sub(r'[^a-z0-9]+', ' ', spoken.lower()).strip()
    if not q.startswith('jarvis ') and q != 'jarvis':
        return Result('none', '', 'Say Jarvis first, then your command.')
    q = q[6:].strip()
    q = re.sub(r'^please | please$', '', q).strip()
    if not q:
        return Result('none', '', 'Ready. Try show Japan or open tracking.')
    # Full matches deliberately reject negations, compound instructions and
    # substring collisions such as "disclose" matching "close".
    if re.fullmatch(r'(?:analyze|analyse|scan|review|cycle) joey(?: s)? locations?', q):
        return Result('joey_scan', 'start', 'Starting the saved three-country tour.')
    m = re.fullmatch(r'(?:show|find|select|bring up|focus|locate|open|go to|take me to) (?:the )?(new zealand|united states|america|japan)', q)
    if m:
        country = {'america': 'united_states'}.get(m[1], m[1].replace(' ', '_'))
        return Result('country', country, 'Selecting ' + m[1].title() + '.')
    groups = [
        ('globe', 'open', r'(?:open|show|display|bring up) (?:the )?globe', 'Opening the globe.'),
        ('globe', 'close', r'(?:close|hide|dismiss) (?:the )?globe', 'Closing the globe.'),
        ('globe', 'reset', r'(?:reset|recenter|centre|center) (?:the )?globe', 'Resetting the globe.'),
        ('identity', 'close', r'(?:close|hide|dismiss) (?:the )?(?:identity|identities|photo)(?: panel)?', 'Closing the identity panel.'),
        ('background', 'cinematic', r'(?:switch to |enable )?(?:cinematic|dark mode|cinema mode)(?: mode)?', 'Switching to cinematic mode.'),
        ('background', 'camera', r'(?:switch to |enable )?(?:camera mode|webcam mode|camera background|live camera|live mode)', 'Enabling camera mode.'),
        ('workspace', 'system', r'(?:open|show|display|bring up) (?:the )?(?:system|diagnostics|system diagnostics)', 'Opening system diagnostics.'),
        ('workspace', 'tracking', r'(?:open|show|display|bring up) (?:the )?(?:hand )?tracking', 'Opening hand tracking.'),
        ('workspace', 'commands', r'(?:open|show|display|bring up) (?:the )?(?:commands|command panel|help panel)', 'Opening commands.'),
        ('workspace', 'close', r'(?:close|hide|dismiss) (?:the )?(?:workspace|window|panel)', 'Closing the workspace.'),
        ('core', 'reset', r'(?:reset|center|centre) (?:the )?(?:hologram|core)', 'Resetting the hologram.'),
        ('ambience', 'mute', r'mute (?:the )?(?:background|ambient|ambience|soundtrack)(?: sound| audio)?', 'Muting ambient sound.'),
        ('ambience', 'unmute', r'unmute (?:the )?(?:background|ambient|ambience|soundtrack)(?: sound| audio)?', 'Restoring ambient sound.'),
    ]
    for command, argument, pattern, response in groups:
        if re.fullmatch(pattern, q):
            return Result(command, argument, response)
    if q in ('help', 'what can you do', 'list commands'):
        return Result('none', '', 'I can show countries, open workspaces, switch backgrounds, reset the hologram, and control the ambience.')
    return Result('unknown', q, 'That is not a built-in command. Please use one command at a time.')
