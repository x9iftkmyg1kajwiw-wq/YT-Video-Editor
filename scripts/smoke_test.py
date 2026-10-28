#!/usr/bin/env python3
"""Generate synthetic footage, run the editor, and verify real encoded output."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from edit import probe, run


def verify(path, duration):
    data = probe(path)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    assert (video['width'], video['height'], video['codec_name'], video['r_frame_rate']) == (1920, 1080, 'h264', '30/1'), video
    assert audio['codec_name'] == 'aac', audio
    assert abs(float(data['format']['duration']) - duration) < 0.15, data['format']
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'])
    print(f'PASS {path.name}: 1920x1080, 30 FPS, H.264/AAC, {data["format"]["duration"]} s; decoded successfully')


def main():
    (ROOT / 'output').mkdir(exist_ok=True)
    (ROOT / 'temp').mkdir(exist_ok=True)
    # FFmpeg refuses to overwrite existing files, protecting prior user material.
    test = ROOT / 'output/test_5s.mp4'
    run(['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-n',
         '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=5',
         '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=5',
         '-c:v', 'libx264', '-threads', '2', '-preset', 'ultrafast',
         '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-t', '5', '-movflags', '+faststart', str(test)])
    verify(test, 5)
    with tempfile.TemporaryDirectory(prefix='smoke-', dir=ROOT / 'temp') as directory:
        directory = Path(directory)
        # Second source intentionally has no audio, testing silence insertion.
        silent = directory / 'silent.mp4'
        run(['ffmpeg', '-hide_banner', '-v', 'error', '-n', '-f', 'lavfi',
             '-i', 'color=c=blue:s=640x480:r=24:d=3', '-an', '-c:v', 'libx264',
             '-threads', '2', '-preset', 'ultrafast', str(silent)])
        for name, clips, fade, duration in [
            ('transition', [{'file': str(test), 'start': 1, 'end': 4}, {'file': str(silent)}], 0.5, 5.5),
            ('cut', [{'file': str(test), 'end': 1}, {'file': str(silent), 'end': 1}], 0, 2),
            ('single', [{'file': str(test), 'start': 1, 'end': 3}], 0.5, 2),
            ('three', [{'file': str(test), 'end': 2}] * 3, 0.5, 5),
        ]:
            output = directory / f'{name}.mp4'
            config = directory / f'{name}.json'
            config.write_text(json.dumps({'clips': clips, 'output': str(output),
                                         'transition_seconds': fade, 'preset': 'ultrafast',
                                         'contrast': 1.02, 'saturation': 1.03}))
            run([sys.executable, str(ROOT / 'scripts/edit.py'), str(config)])
            verify(output, duration)
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/edit.py'), str(config)], capture_output=True)
            assert result.returncode != 0 and b'Refusing to overwrite' in result.stderr
    print('PASS: transitions, trimming, silent input, hard cuts, single clip and overwrite protection')


if __name__ == '__main__':
    main()
