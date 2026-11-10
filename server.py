#!/usr/bin/env python3
"""极简静态服务器：把当前目录当静态站点伺服。给 Railway 用。"""
import http.server
import os
import socketserver

PORT = int(os.environ.get("PORT", "8080"))
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", PORT), Handler) as httpd:
        print("serving on 0.0.0.0:%d" % PORT, flush=True)
        httpd.serve_forever()
