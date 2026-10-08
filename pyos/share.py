# pyos/share.py - move files between devices on the same network (phone <-> PC, PythonOS <-> PythonOS)
#
#   SendServer     serves ONE file at an unguessable link; any browser, curl or `share get` can download it
#   ReceiveServer  serves an upload page (and accepts curl -T); everything uploaded lands in one folder
#
# Safety: every URL contains a random token, anything else is a plain 404 (no directory listing, no file names
# leaked); uploads are size-limited and their names are cleaned so they can only create files in the chosen folder;
# a server stops by itself after the first download / after a timeout.
import html
import http.server
import os
import queue
import re
import secrets
import socket
import threading
import time
import urllib.parse

MAX_UPLOAD = 500 * 1024 * 1024
CHUNK = 256 * 1024


def lan_addresses():
    """This device's IPv4 addresses on the local network (best guess first)."""
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))       # no packet is sent; this just picks the outgoing interface
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        import psutil
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith("127.") and a.address not in found:
                    found.append(a.address)
    except Exception:
        pass
    return [a for a in found if not a.startswith("0.")] or ["127.0.0.1"]


def safe_filename(name):
    """A file name that can only ever create a file in the target folder."""
    name = os.path.basename(str(name).replace("\\", "/"))
    name = re.sub(r"[^\w.\- ()\[\]]", "_", name, flags=re.UNICODE).strip(" .")
    return (name[:120] or "file")


def unique_path(folder, name):
    base, ext = os.path.splitext(name)
    candidate, n = os.path.join(folder, name), 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{base} ({n}){ext}")
        n += 1
    return candidate


class _QuietHTTPServer(http.server.ThreadingHTTPServer):
    """A client that hangs up mid-transfer is normal; never print a traceback onto the user's screen for it."""

    def handle_error(self, request, client_address):
        pass


class _Server:
    """Common start/stop plumbing."""

    def __init__(self, host="0.0.0.0", port=0):  # nosec B104 - sharing on the local network is the point; a token guards it
        self.token = secrets.token_urlsafe(9)
        self.events = queue.Queue()      # ("sent" | "received" | "error", text) for the command to print
        self.done = threading.Event()
        self.host, self.port = host, port
        self._httpd = None

    def start(self):
        self._httpd = _QuietHTTPServer((self.host, self.port), self._handler())
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, name="share", daemon=True).start()
        return self

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def urls(self):
        return [self._url(a) for a in (lan_addresses() if self.host in ("0.0.0.0", "") else [self.host])]  # nosec B104 - the "listen everywhere" setting, not a bind

    def wait(self, timeout, on_event):
        """Block until done, the timeout, or Ctrl+C; calls on_event(kind, text) as things happen."""
        end = time.time() + timeout
        try:
            while not self.done.is_set() and time.time() < end:
                try:
                    on_event(*self.events.get(timeout=0.3))
                except queue.Empty:
                    pass
            while not self.events.empty():
                on_event(*self.events.get())
        except KeyboardInterrupt:
            return "cancelled"
        return "done" if self.done.is_set() else "timeout"


class SendServer(_Server):
    def __init__(self, path, keep=False, **kw):
        super().__init__(**kw)
        self.path, self.keep = path, keep
        self.name = safe_filename(os.path.basename(path))
        self.downloads = 0

    def _url(self, host):
        return f"http://{host}:{self.port}/t/{self.token}/{urllib.parse.quote(self.name)}"

    def _handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parts = urllib.parse.urlsplit(self.path).path.split("/")
                if len(parts) < 3 or parts[1] != "t" or not secrets.compare_digest(parts[2], server.token) or len(parts) > 4:
                    return self._plain(404, "Not found")
                try:
                    size = os.path.getsize(server.path)
                    f = open(server.path, "rb")
                except OSError:
                    return self._plain(404, "Not found")
                with f:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(size))
                    self.send_header("Content-Disposition", f'attachment; filename="{server.name}"')
                    self.end_headers()
                    try:
                        while True:
                            chunk = f.read(CHUNK)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    except OSError:
                        server.events.put(("error", f"{self.client_address[0]} stopped the download"))
                        return
                server.downloads += 1
                server.events.put(("sent", f"{server.name} sent to {self.client_address[0]}"))
                if not server.keep:
                    server.done.set()

            def _plain(self, code, text):
                body = text.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


UPLOAD_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Send files to PythonOS</title><style>
body{font-family:system-ui,sans-serif;background:#0c0c0c;color:#e6e6e6;max-width:30rem;margin:2rem auto;padding:0 1rem}
h1{font-size:1.3rem}.drop{border:2px dashed #4fe3c1;border-radius:12px;padding:2rem;text-align:center}
button{background:#4fe3c1;color:#0c0c0c;border:0;border-radius:8px;padding:.7rem 1.2rem;font-size:1rem}
li{margin:.4rem 0;word-break:break-all}.ok{color:#4fe3c1}.bad{color:#ff6b6b}</style></head><body>
<h1>Send files to PythonOS</h1><div class="drop"><input id="f" type="file" multiple><p><button onclick="go()">Send</button></p></div>
<ul id="log"></ul><script>
async function go(){const files=document.getElementById('f').files,log=document.getElementById('log');
for(const file of files){const li=document.createElement('li');li.textContent=file.name+' ...';log.appendChild(li);
try{const r=await fetch('up?name='+encodeURIComponent(file.name),{method:'POST',body:file});
li.textContent=file.name+' - '+(await r.text());li.className=r.ok?'ok':'bad';}catch(e){li.textContent=file.name+' - failed';li.className='bad';}}}
</script></body></html>"""


class ReceiveServer(_Server):
    def __init__(self, folder, max_files=None, **kw):
        super().__init__(**kw)
        self.folder, self.max_files = folder, max_files
        self.count = 0

    def _url(self, host):
        return f"http://{host}:{self.port}/u/{self.token}/"

    def _handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _plain(self, code, text):
                body = text.encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route(self):
                split = urllib.parse.urlsplit(self.path)
                parts = split.path.split("/")
                if len(parts) < 3 or parts[1] != "u" or not secrets.compare_digest(parts[2], server.token):
                    return None
                return parts[3:], urllib.parse.parse_qs(split.query)

            def do_GET(self):
                route = self._route()
                if route is None or route[0] not in ([], [""]):
                    return self._plain(404, "Not found")
                body = UPLOAD_PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                route = self._route()
                if route is None or route[0] != ["up"]:
                    return self._plain(404, "Not found")
                self._store((route[1].get("name") or ["file"])[0])

            def do_PUT(self):                      # curl -T file http://host:port/u/TOKEN/up/
                route = self._route()
                if route is None or not route[0] or route[0][0] != "up":
                    return self._plain(404, "Not found")
                self._store(urllib.parse.unquote(route[0][-1]) or "file")

            def _store(self, name):
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    return self._plain(411, "Length required")
                if length > MAX_UPLOAD:
                    return self._plain(413, f"Too big (limit {MAX_UPLOAD // (1024 * 1024)} MB)")
                os.makedirs(server.folder, exist_ok=True)
                target = unique_path(server.folder, safe_filename(name))
                part = target + ".part"
                remaining = length
                try:
                    with open(part, "wb") as f:
                        while remaining > 0:
                            chunk = self.rfile.read(min(CHUNK, remaining))
                            if not chunk:
                                raise OSError("connection closed early")
                            f.write(chunk)
                            remaining -= len(chunk)
                    os.replace(part, target)
                except OSError as e:
                    try:
                        os.remove(part)
                    except OSError:
                        pass
                    server.events.put(("error", f"upload of {name} failed: {e}"))
                    return self._plain(500, "Failed")
                server.count += 1
                server.events.put(("received", f"{os.path.basename(target)} ({length} bytes) from {self.client_address[0]}"))
                self._plain(200, f"saved as {os.path.basename(target)}")
                if server.max_files and server.count >= server.max_files:
                    server.done.set()

        return Handler
