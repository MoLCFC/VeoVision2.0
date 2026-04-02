"""
Better HTTP Server with Range Request Support for Video Playback
This server supports HTTP range requests which are needed for MP4 video streaming.
"""

import http.server
import os
import socketserver


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with support for range requests (for video streaming)"""

    def do_GET(self):
        """Handle GET request with range support"""
        self.range_from = None
        if 'Range' in self.headers:
            try:
                range_header = self.headers['Range']
                range_match = range_header.replace('bytes=', '').split('-')
                self.range_from = int(range_match[0])
                self.range_to = int(range_match[1]) if range_match[1] else None
            except Exception:
                pass

        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def send_head(self):
        """Common code for GET and HEAD commands with range support"""
        path = self.translate_path(self.path)

        if os.path.isdir(path):
            return http.server.SimpleHTTPRequestHandler.send_head(self)

        try:
            f = open(path, 'rb')
        except OSError:
            return http.server.SimpleHTTPRequestHandler.send_head(self)

        fs = os.fstat(f.fileno())
        file_len = fs.st_size

        if self.range_from is not None:
            self.send_response(206)  # Partial Content
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")

            if self.range_to is None or self.range_to >= file_len:
                self.range_to = file_len - 1

            self.send_header("Content-Range", f"bytes {self.range_from}-{self.range_to}/{file_len}")
            self.send_header("Content-Length", str(self.range_to - self.range_from + 1))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()

            f.seek(self.range_from)
            return f
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(file_len))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f


def run_server(port=5500):
    """Run the HTTP server with range request support"""
    handler = RangeRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"========================================")
        print(f"  VeoVision Server with Range Support")
        print(f"========================================")
        print(f"Server running at: http://localhost:{port}")
        print(f"Open in browser: http://localhost:{port}/veo_frontend/")
        print(f"Press Ctrl+C to stop")
        print(f"========================================\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    if not os.path.exists("veo_frontend"):
        print("ERROR: Please run this script from the VeoVision repository (veo_frontend missing).")
        print("Current directory:", os.getcwd())
        exit(1)

    run_server(5600)
