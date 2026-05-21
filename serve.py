"""
Pi Slice server.
Setup (run once):  pip install flask imageio-ffmpeg
Start:             python serve.py
"""
import os, json, subprocess, tempfile, shutil, atexit
from flask import Flask, request, send_file, jsonify, send_from_directory

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = shutil.which('ffmpeg')

TEMP_DIR = tempfile.mkdtemp(prefix='pi_slice_')
atexit.register(shutil.rmtree, TEMP_DIR, True)

uploads = {}   # token -> filepath  (videos AND audio share this dict)
clips   = {}   # clip_id -> filepath (served via /clip/<id>)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10 GB


@app.after_request
def add_headers(r):
    r.headers['Cross-Origin-Opener-Policy']   = 'same-origin'
    r.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    r.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
    return r


@app.route('/')
@app.route('/video-splicer.html')
def index():
    return send_from_directory('.', 'video-splicer.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


@app.route('/api/status')
def status():
    return jsonify({'ffmpeg': bool(FFMPEG)})


# ── upload (video or audio) ───────────────────────────────────────────────────
@app.route('/api/upload', methods=['POST'])
def upload():
    filename = request.headers.get('X-Filename', 'file')
    ext      = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    size_mb  = (request.content_length or 0) // (1024 * 1024)
    print(f'Receiving: {filename}  ({size_mb} MB)')

    fd, path = tempfile.mkstemp(suffix='.' + ext, dir=TEMP_DIR)
    os.close(fd)

    with open(path, 'wb') as f:
        while True:
            chunk = request.stream.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)

    token = hex(abs(hash(path)))
    uploads[token] = path
    print(f'Saved: {os.path.getsize(path) // (1024*1024)} MB  token={token}')
    return jsonify({'token': token})


# ── trim single segment ───────────────────────────────────────────────────────
@app.route('/clip/<clip_id>')
def serve_clip(clip_id):
    path = clips.get(clip_id)
    if not path or not os.path.exists(path):
        return 'Clip not found (may have expired — regenerate the link)', 404
    ext  = path.rsplit('.', 1)[-1].lower()
    mime = 'image/gif' if ext == 'gif' else 'video/' + ext
    return send_file(path, mimetype=mime, conditional=True)


@app.route('/api/clip_link', methods=['POST'])
def clip_link():
    """Trim a segment, store it server-side, return a URL instead of downloading."""
    if not FFMPEG:
        return jsonify({'error': 'ffmpeg not found'}), 503
    body      = request.get_json()
    token     = body.get('token')
    start     = float(body.get('start', 0))
    duration  = float(body.get('duration', 0))
    name      = body.get('name', 'clip')
    fmt       = body.get('format', 'original')
    crf       = str(max(18, min(35, int(body.get('crf', 25)))))
    compress  = bool(body.get('compress', True))

    src = uploads.get(token)
    if not src or not os.path.exists(src):
        return jsonify({'error': 'Video not found — re-import your video.'}), 404

    src_ext = src.rsplit('.', 1)[-1].lower()
    out_ext = {'mp4': 'mp4', 'gif': 'gif', 'webm': 'webm'}.get(fmt, src_ext)

    fd, out = tempfile.mkstemp(suffix='.' + out_ext, dir=TEMP_DIR)
    os.close(fd)

    if fmt == 'gif':
        cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
               '-vf', f'fps=10,scale=480:-1:flags=lanczos,'
                      f'split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse', out]
    elif not compress:
        cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
               '-c', 'copy', '-avoid_negative_ts', 'make_zero', out]
    elif fmt == 'webm' or (fmt == 'original' and src_ext == 'webm'):
        cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
               '-c:v', 'libvpx-vp9', '-crf', crf, '-b:v', '0', '-c:a', 'libopus', out]
    else:
        cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
               '-c:v', 'libx264', '-crf', crf, '-c:a', 'aac',
               '-movflags', '+faststart', out]

    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        return jsonify({'error': 'ffmpeg error: ' + r.stderr.decode(errors='replace')[-200:]}), 500

    import uuid
    clip_id = uuid.uuid4().hex[:12]
    clips[clip_id] = out
    safe = _safe_name(name) or 'clip'
    return jsonify({'url': f'/clip/{clip_id}', 'filename': safe + '.' + out_ext})


@app.route('/api/export_package', methods=['POST'])
def export_package():
    """Trim all segments, bundle with instructions markdown, return as ZIP."""
    if not FFMPEG:
        return jsonify({'error': 'ffmpeg not found'}), 503

    body      = request.get_json()
    segs      = body.get('segments', [])
    markdown  = body.get('markdown', '')
    zip_name  = _safe_name(body.get('zipName', 'pi_slice')) or 'pi_slice'

    import zipfile, io
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add instructions markdown
        zf.writestr('instructions.md', markdown.encode('utf-8'))

        for seg in segs:
            token    = seg.get('token')
            start    = float(seg.get('start', 0))
            duration = float(seg.get('duration', 0))
            name     = seg.get('name', 'clip')
            idx      = int(seg.get('index', 1))
            fmt      = seg.get('format', 'original')
            crf      = str(max(18, min(35, int(seg.get('crf', 25)))))
            compress = bool(seg.get('compress', True))

            src = uploads.get(token)
            if not src or not os.path.exists(src):
                print(f'Skipping segment {idx} — source not found')
                continue

            src_ext = src.rsplit('.', 1)[-1].lower()
            out_ext = {'mp4': 'mp4', 'gif': 'gif', 'webm': 'webm'}.get(fmt, src_ext)
            fd, out = tempfile.mkstemp(suffix='.' + out_ext, dir=TEMP_DIR)
            os.close(fd)

            try:
                if not compress:
                    cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                           '-c', 'copy', '-avoid_negative_ts', 'make_zero', out]
                elif fmt == 'webm' or (fmt == 'original' and src_ext == 'webm'):
                    cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                           '-c:v', 'libvpx-vp9', '-crf', crf, '-b:v', '0', '-c:a', 'libopus', out]
                else:
                    cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                           '-c:v', 'libx264', '-crf', crf, '-c:a', 'aac',
                           '-movflags', '+faststart', out]

                r = subprocess.run(cmd, capture_output=True)
                if r.returncode != 0:
                    print(f'ffmpeg error for segment {idx}:', r.stderr.decode(errors='replace')[-200:])
                    continue

                safe     = _safe_name(name) or f'step_{idx:02d}'
                filename = f'{idx:02d}_{safe}.{out_ext}'
                print(f'Adding to ZIP: {filename}')
                with open(out, 'rb') as f:
                    zf.writestr(filename, f.read())
            finally:
                try: os.unlink(out)
                except: pass

    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'{zip_name}_export.zip')


@app.route('/api/thumbnail', methods=['POST'])
def thumbnail():
    if not FFMPEG:
        return jsonify({'error': 'ffmpeg not found'}), 503
    body  = request.get_json()
    token = body.get('token')
    time  = float(body.get('time', 0))
    src   = uploads.get(token)
    if not src or not os.path.exists(src):
        return jsonify({'error': 'not found'}), 404
    fd, out = tempfile.mkstemp(suffix='.jpg', dir=TEMP_DIR)
    os.close(fd)
    try:
        subprocess.run([
            FFMPEG, '-y', '-ss', str(time), '-i', src,
            '-vframes', '1', '-vf', 'scale=240:-1', '-q:v', '4', out
        ], capture_output=True)
        return send_file(out, mimetype='image/jpeg')
    finally:
        try: os.unlink(out)
        except: pass


@app.route('/api/trim', methods=['POST'])
def trim():
    if not FFMPEG:
        return jsonify({'error': 'ffmpeg not found. Run: pip install imageio-ffmpeg'}), 503

    body      = request.get_json()
    token     = body.get('token')
    start     = float(body.get('start',    0))
    duration  = float(body.get('duration', 0))
    name      = body.get('name', 'segment')
    fmt       = body.get('format',   'original')
    crf       = str(max(18, min(35, int(body.get('crf', 25)))))
    compress  = bool(body.get('compress', True))
    gif_fps   = max(1,   min(30,   int(body.get('gifFps',   10))))
    gif_width = max(100, min(1920, int(body.get('gifWidth', 480))))

    src = uploads.get(token)
    if not src or not os.path.exists(src):
        return jsonify({'error': 'Video not found on server — re-import your video.'}), 404

    src_ext = src.rsplit('.', 1)[-1].lower()
    out_ext = {'mp4': 'mp4', 'gif': 'gif', 'webm': 'webm'}.get(fmt, src_ext)

    fd, out = tempfile.mkstemp(suffix='.' + out_ext, dir=TEMP_DIR)
    os.close(fd)

    try:
        print(f'Trim "{name}" → {out_ext} (compress={compress}, crf={crf}):  {start:.2f}s + {duration:.2f}s')

        if fmt == 'gif':
            # GIF always re-encodes
            cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                   '-vf', f'fps={gif_fps},scale={gif_width}:-1:flags=lanczos,'
                          f'split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse', out]
        elif not compress:
            # No compression — fast stream copy regardless of format
            cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                   '-c', 'copy', '-avoid_negative_ts', 'make_zero', out]
        elif fmt == 'webm' or (fmt == 'original' and src_ext == 'webm'):
            cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                   '-c:v', 'libvpx-vp9', '-crf', crf, '-b:v', '0', '-c:a', 'libopus', out]
        else:
            # mp4, original non-webm — encode with libx264 + CRF
            cmd = [FFMPEG, '-y', '-ss', str(start), '-i', src, '-t', str(duration),
                   '-c:v', 'libx264', '-crf', crf, '-c:a', 'aac',
                   '-movflags', '+faststart', out]

        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            err = r.stderr.decode(errors='replace')[-400:]
            print('ffmpeg error:', err)
            return jsonify({'error': 'ffmpeg error: ' + err}), 500

        safe     = _safe_name(name)
        out_name = safe + '.' + out_ext
        mime     = 'image/gif' if out_ext == 'gif' else 'video/' + out_ext
        print(f'Done: {out_name}  ({os.path.getsize(out)//1024} KB)')
        return send_file(out, as_attachment=True, download_name=out_name, mimetype=mime)
    finally:
        try: os.unlink(out)
        except: pass


# ── combine multiple segments into one file ───────────────────────────────────
@app.route('/api/combine', methods=['POST'])
def combine():
    if not FFMPEG:
        return jsonify({'error': 'ffmpeg not found. Run: pip install imageio-ffmpeg'}), 503

    body       = request.get_json()
    segs       = body.get('segments', [])
    fmt        = body.get('format', 'mp4')
    audio_tok  = body.get('audioToken')
    audio_mode = body.get('audioMode', 'replace')   # replace | mix
    out_name   = _safe_name(body.get('combinedName', 'combined'))

    if not segs:
        return jsonify({'error': 'No segments provided'}), 400

    out_ext   = 'webm' if fmt == 'webm' else 'mp4'
    clip_files = []
    extra_temps = []

    try:
        # 1. Extract each segment to a temp clip
        for i, seg in enumerate(segs):
            src = uploads.get(seg.get('token'))
            if not src or not os.path.exists(src):
                return jsonify({'error': f'Source video missing for segment {i+1} — re-import videos.'}), 404

            src_ext = src.rsplit('.', 1)[-1].lower()
            fd, clip = tempfile.mkstemp(suffix='.' + src_ext, dir=TEMP_DIR)
            os.close(fd)
            clip_files.append(clip)

            r = subprocess.run([
                FFMPEG, '-y',
                '-ss', str(float(seg.get('start', 0))),
                '-i', src,
                '-t', str(float(seg.get('duration', 0))),
                '-c', 'copy', '-avoid_negative_ts', 'make_zero', clip
            ], capture_output=True)

            if r.returncode != 0:
                return jsonify({'error': f'Failed to extract segment {i+1}: '
                                + r.stderr.decode(errors='replace')[-200:]}), 500

        # 2. Concatenate
        fd, combined = tempfile.mkstemp(suffix='.' + out_ext, dir=TEMP_DIR)
        os.close(fd)
        extra_temps.append(combined)
        print(f'Combining {len(clip_files)} clips → {out_ext}')

        if len(clip_files) == 1:
            if fmt == 'webm':
                cmd = [FFMPEG, '-y', '-i', clip_files[0],
                       '-c:v', 'libvpx-vp9', '-c:a', 'libopus', combined]
            else:
                cmd = [FFMPEG, '-y', '-i', clip_files[0], '-c', 'copy', combined]
        else:
            fd2, lst = tempfile.mkstemp(suffix='.txt', dir=TEMP_DIR)
            extra_temps.append(lst)
            with os.fdopen(fd2, 'w') as f:
                for clip in clip_files:
                    f.write(f"file '{clip}'\n")
            if fmt == 'webm':
                cmd = [FFMPEG, '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                       '-c:v', 'libvpx-vp9', '-c:a', 'libopus', combined]
            else:
                cmd = [FFMPEG, '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                       '-c', 'copy', combined]

        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            err = r.stderr.decode(errors='replace')[-400:]
            print('Concat error:', err)
            return jsonify({'error': 'Combine failed: ' + err}), 500

        # 3. Optional audio overlay
        final = combined
        if audio_tok and audio_mode in ('replace', 'mix'):
            audio_src = uploads.get(audio_tok)
            if audio_src and os.path.exists(audio_src):
                fd3, with_audio = tempfile.mkstemp(suffix='.' + out_ext, dir=TEMP_DIR)
                os.close(fd3)
                extra_temps.append(with_audio)

                if audio_mode == 'replace':
                    acmd = [FFMPEG, '-y', '-i', combined, '-i', audio_src,
                            '-c:v', 'copy', '-map', '0:v', '-map', '1:a',
                            '-shortest', with_audio]
                else:
                    acmd = [FFMPEG, '-y', '-i', combined, '-i', audio_src,
                            '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first',
                            '-c:v', 'copy', with_audio]

                r2 = subprocess.run(acmd, capture_output=True)
                if r2.returncode == 0:
                    final = with_audio
                else:
                    print('Audio overlay warning (skipped):', r2.stderr.decode(errors='replace')[-200:])

        size = os.path.getsize(final)
        print(f'Combined: {out_name}.{out_ext}  ({size//(1024*1024)} MB)')
        return send_file(final, as_attachment=True,
                         download_name=out_name + '.' + out_ext,
                         mimetype='video/' + out_ext)
    finally:
        for f in clip_files + extra_temps:
            try: os.unlink(f)
            except: pass


def _safe_name(s):
    return (''.join(c for c in s if c.isalnum() or c in ' _-')
            .strip().replace(' ', '_'))[:60] or 'output'


if not FFMPEG:
    print('WARNING: ffmpeg not found.')
    print('Run:  pip install imageio-ffmpeg\n')

print('Server →  http://localhost:8080/video-splicer.html')
print(f'ffmpeg  →  {FFMPEG or "NOT FOUND"}')
print('Ctrl+C to stop.\n')
app.run(host='0.0.0.0', port=8080, debug=False)
