"""Prepare a private development scene from an existing JARVIS release on macOS."""
import argparse
import functools
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess

REPO = Path(__file__).resolve().parents[1]
UTILS = Path('/Applications/TouchDesigner.app/Contents/MacOS')


def copy_local_file(source, destination):
    source, destination = Path(source), Path(destination)
    info = source.stat()
    if getattr(info, 'st_flags', 0) & getattr(stat, 'SF_DATALESS', 0x40000000):
        raise ValueError('Download this iCloud placeholder in Finder before retrying: ' + str(source))
    # Ordinary byte copying avoids propagating dataless clone placeholders.
    with source.open('rb') as src, destination.open('wb') as dst:
        shutil.copyfileobj(src, dst)
    destination.chmod(stat.S_IMODE(info.st_mode))
    return str(destination)


def load_review_manifest(path):
    review = json.loads(path.read_text(encoding='utf-8'))
    if review.get('reviewed') is not True or not isinstance(review.get('files'), dict):
        raise ValueError('A completed privacy review manifest is required.')
    approved = review['files']
    for name, digest in approved.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid reviewed-file entry.')
    return approved


def copy_reviewed_file(source, destination, *, root, approved):
    source = Path(source)
    resolved = source.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('The source points outside the reviewed project.')
    relative = source.relative_to(root).as_posix()
    if relative not in approved:
        raise ValueError('An unreviewed source file was excluded.')
    if getattr(source.stat(), 'st_flags', 0) & getattr(stat, 'SF_DATALESS', 0x40000000):
        raise ValueError('Download the reviewed file in Finder before retrying.')
    # Write the same in-memory bytes that were verified, so a later source
    # change cannot slip unreviewed content into the output.
    info = source.stat()
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != approved[relative]:
        raise ValueError('A reviewed file changed; repeat the privacy review.')
    destination = Path(destination)
    destination.write_bytes(data)
    destination.chmod(stat.S_IMODE(info.st_mode))
    return str(destination)


def prepare(source, output, review_manifest):
    source, output = source.resolve(), output.resolve()
    approved = load_review_manifest(review_manifest)
    if output.exists():
        raise ValueError('Choose a new output folder; existing scenes are preserved.')
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Source and output must be separate folders.')
    if not (source / 'Hand_Tracking_Jarvis_V1.toe').is_file():
        raise ValueError('The source must contain Hand_Tracking_Jarvis_V1.toe.')
    shutil.copytree(source, output, copy_function=functools.partial(copy_reviewed_file, root=source, approved=approved),
                    ignore=shutil.ignore_patterns('.venv', '__pycache__', '*.zip',
                        'Backup', '.DS_Store', 'voice_*.json', 'voice_service.lock', 'PRIVACY_REVIEW.json'))
    for item in (REPO / 'JARVIS_VOICE_V20').iterdir():
        if item.is_file() and item.suffix in ('.py', '.json', '.txt', '.command'):
            copy_local_file(item, output / 'JARVIS_VOICE_V20' / item.name)
    scene = output / 'Hand_Tracking_Jarvis_V1.toe'
    result = subprocess.run([str(UTILS / 'toeexpand'), str(scene)], capture_output=True, text=True)
    expanded = Path(str(scene) + '.dir')
    if not expanded.is_dir():
        raise RuntimeError('toeexpand failed: ' + result.stdout + result.stderr)
    hud = expanded / 'project1/gesture_hud'
    for name, path in {
            'jv20_voice_bridge': REPO / 'JARVIS_VOICE_V20/JV20_TOUCHDESIGNER_BRIDGE.py',
            'render_callbacks': REPO / 'touchdesigner/render_callbacks.py'}.items():
        target = hud / (name + '.text')
        data, body = target.read_bytes(), path.read_bytes()
        if struct.unpack('>I', data[23:27])[0] != len(data) - 27:
            raise ValueError('Unexpected TouchDesigner DAT format: ' + str(target))
        target.write_bytes(data[:23] + struct.pack('>I', len(body)) + body)
    old, new = str(source).encode(), str(output).encode()
    for item in expanded.rglob('*'):
        if item.suffix not in ('.parm', '.table', '.text'):
            continue
        data = item.read_bytes()
        if old not in data:
            continue
        if item.suffix == '.table':
            for value in set(re.findall(re.escape(old) + rb'[^\x00\r\n]*', data)):
                changed = value.replace(old, new)
                data = data.replace(struct.pack('>I', len(value)) + value,
                                    struct.pack('>I', len(changed)) + changed)
        elif item.suffix == '.text':
            body = data[27:].replace(old, new)
            data = data[:23] + struct.pack('>I', len(body)) + body
        else:
            data = data.replace(old, new)
        item.write_bytes(data)
    scene.rename(output / 'Hand_Tracking_Jarvis_V1.before-updates.toe')
    result = subprocess.run([str(UTILS / 'toecollapse'), str(scene)], capture_output=True, text=True)
    if not scene.is_file():
        raise RuntimeError('toecollapse failed; expanded source preserved: ' + result.stdout + result.stderr)
    print('Prepared private development scene:', scene)
    print('The original folder is unchanged. Live hardware validation is still required.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--review-manifest', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.release, args.output, args.review_manifest)
