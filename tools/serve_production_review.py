"""Local report server with byte ranges for media playback and seeking."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'artifacts/production-lab-20261003/review'


class MediaHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        self.remaining = None
        path = Path(self.translate_path(self.path)).resolve()
        directory = Path(self.directory).resolve()
        if not path.is_relative_to(directory):
            self.send_error(403)
            return None
        if not self.headers.get('Range') or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', self.headers['Range'].strip())
        try:
            if not match or not size:
                raise ValueError
            first, last = match.groups()
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                length = int(last)
                if length <= 0:
                    raise ValueError
                start, end = max(0, size - length), size - 1
            if start > end or start >= size:
                raise ValueError
        except (ValueError, TypeError):
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return None
        stream = path.open('rb')
        stream.seek(start)
        self.remaining = end - start + 1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(self.remaining))
        self.send_header('Last-Modified', self.date_time_string(path.stat().st_mtime))
        self.end_headers()
        return stream

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def copyfile(self, source, outputfile):
        if self.remaining is None:
            return super().copyfile(source, outputfile)
        remaining = self.remaining
        while remaining:
            block = source.read(min(64 * 1024, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8842)
    args = parser.parse_args()
    # Serve only the exported report, never the project or provider credentials.
    handler = partial(MediaHandler, directory=str(DEFAULT))
    with ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server:
        print(f'REVIEW_SERVER http://127.0.0.1:{args.port}/', flush=True)
        server.serve_forever()
