#!/usr/bin/env python3
"""Config-driven, local FFmpeg editing. All paths are relative to project root."""
import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    subprocess.run(args, check=True)


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', str(path)]))


def number(value, name, low, high):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value


def edit(config):
    clips = config['clips']
    if not isinstance(clips, list) or not clips:
        raise ValueError('clips must be a nonempty list')
    fade = number(config.get('transition_seconds', 0.5), 'transition_seconds', 0, 10)
    brightness = number(config.get('brightness', 0), 'brightness', -1, 1)
    contrast = number(config.get('contrast', 1), 'contrast', 0, 3)
    saturation = number(config.get('saturation', 1), 'saturation', 0, 3)
    crf = int(number(config.get('crf', 20), 'crf', 0, 51))
    preset = config.get('preset', 'medium')
    if preset not in ('ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'):
        raise ValueError('Unsupported x264 preset')
    output = (ROOT / config.get('output', 'output/finished.mp4')).resolve()
    if output.suffix.lower() != '.mp4':
        raise ValueError('Output must be an MP4')
    if output.exists():
        raise ValueError(f'Refusing to overwrite {output}')
    prepared = []
    for clip in clips:
        source = (ROOT / clip['file']).resolve()
        info = probe(source)
        if not any(s['codec_type'] == 'video' for s in info['streams']):
            raise ValueError(f'No video in {source}')
        duration = float(info['format']['duration'])
        start = number(clip.get('start', 0), 'start', 0, duration)
        end = number(clip.get('end', duration), 'end', start, duration)
        # Quantize to output frames so xfade offsets match encoded durations.
        frames = int((end - start) * 30)
        length = frames / 30
        if frames < 1 or (len(clips) > 1 and fade and length <= 2 * fade):
            raise ValueError('Each clip must contain at least one frame and exceed twice the transition duration')
        prepared.append((source, start, length, frames,
                         any(s['codec_type'] == 'audio' for s in info['streams'])))
    output.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / 'temp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='edit-', dir=ROOT / 'temp') as work:
        work = Path(work)
        for i, (source, start, length, frames, audio) in enumerate(prepared):
            cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-n',
                   '-ss', str(start), '-i', str(source)]
            if not audio:
                cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            cmd += ['-map', '0:v:0', '-map', '0:a:0' if audio else '1:a:0',
                    '-t', str(length), '-vf',
                    f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,eq=brightness={brightness}:contrast={contrast}:saturation={saturation},format=yuv420p',
                    '-af', 'aresample=48000,aformat=channel_layouts=stereo,apad',
                    '-c:v', 'libx264', '-threads', '2', '-preset', preset, '-crf', str(crf),
                    '-c:a', 'aac', '-b:a', '192k', str(work / f'{i}.mp4')]
            run(cmd)
        cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-n', '-filter_complex_threads', '1']
        for i in range(len(prepared)):
            cmd += ['-i', str(work / f'{i}.mp4')]
        filters = []
        for i in range(len(prepared)):
            filters += [f'[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps=30[v{i}]',
                        f'[{i}:a]asetpts=PTS-STARTPTS[a{i}]']
        v, a, elapsed = 'v0', 'a0', prepared[0][2]
        for i in range(1, len(prepared)):
            nv, na = f'joinv{i}', f'joina{i}'
            if fade:
                filters += [f'[{v}][v{i}]xfade=transition=fade:duration={fade}:offset={elapsed-fade},fps=30[{nv}]',
                            f'[{a}][a{i}]acrossfade=d={fade}:c1=tri:c2=tri[{na}]']
            else:
                filters += [f'[{v}][{a}][v{i}][a{i}]concat=n=2:v=1:a=1[{nv}][{na}]']
            v, a = nv, na
            elapsed += prepared[i][2] - fade
        filters += [f'[{a}]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[normalized]']
        # Render inside temporary workspace; publish only a complete successful output.
        rendered = work / 'finished.mp4'
        cmd += ['-filter_complex', ';'.join(filters), '-map', f'[{v}]', '-map', '[normalized]',
                '-c:v', 'libx264', '-threads', '2', '-preset', preset, '-crf', str(crf),
                '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k',
                '-t', str(elapsed), '-movflags', '+faststart', str(rendered)]
        run(cmd)
        # Exclusive creation also protects against another job producing the same path.
        with output.open('xb') as target, rendered.open('rb') as source:
            shutil.copyfileobj(source, target)
    print(f'Exported: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            parser.error(f'{tool} is not installed')
    try:
        edit(json.loads(args.config.read_text()))
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Editing failed: {exc}\n')


if __name__ == '__main__':
    main()
