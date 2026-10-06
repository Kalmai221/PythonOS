"""Tests the AI Assistant app against a small local server that speaks each service streaming format (no network, no keys)."""
import importlib.util, json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("assistant_run", os.path.join(REPO, "online_packages", "utilities", "assistant", "run.py"))
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)

seen = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/event-stream"):
        data = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        seen.append(("GET", self.path, dict(self.headers)))
        if self.path.endswith("/models"):
            if "v1beta" in self.path:
                self._send(200, json.dumps({"models": [{"name": "models/gem-a", "supportedGenerationMethods": ["generateContent"]}, {"name": "models/emb", "supportedGenerationMethods": ["embedContent"]}]}), "application/json")
            else:
                self._send(200, json.dumps({"data": [{"id": "m-b"}, {"id": "m-a"}]}), "application/json")
        elif self.path == "/api/tags":
            self._send(200, json.dumps({"models": [{"name": "llama3.2"}]}), "application/json")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(("POST", self.path, dict(self.headers), body))
        if self.headers.get("authorization") == "Bearer bad":
            return self._send(401, json.dumps({"error": {"message": "Incorrect API key"}}), "application/json")
        if self.path.endswith("/chat/completions"):
            self._send(200, 'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\ndata: {"choices":[{"delta":{"content":"lo"}}]}\n\ndata: [DONE]\n\n')
        elif self.path.endswith("/messages"):
            self._send(200, 'event: message_start\ndata: {"type":"message_start"}\n\nevent: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hi "}}\n\nevent: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"there"}}\n\n')
        elif "streamGenerateContent" in self.path:
            self._send(200, 'data: {"candidates":[{"content":{"parts":[{"text":"Gem"}]}}]}\n\ndata: {"candidates":[{"content":{"parts":[{"text":"ini"}]}}]}\n\n')
        elif self.path == "/api/chat":
            self._send(200, '{"message":{"content":"Lla"},"done":false}\n{"message":{"content":"ma"},"done":false}\n{"done":true}\n', "application/x-ndjson")


server = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
root = f"http://127.0.0.1:{server.server_port}"
msgs = [{"role": "user", "content": "hi"}]

def run(provider, key="k", model="m", base=None):
    cfg = {"provider": provider, "key": key, "model": model, "base": base or root + {"anthropic": "/v1", "gemini": "/v1beta", "ollama": "", "openai": "/v1", "openrouter": "/v1", "custom": "/v1"}[provider]}
    return "".join(a.stream_answer(cfg, msgs, "be brief")), cfg

for provider, want in (("openai", "Hello"), ("custom", "Hello"), ("openrouter", "Hello"), ("anthropic", "Hi there"), ("gemini", "Gemini"), ("ollama", "Llama")):
    got, cfg = run(provider)
    assert got == want, (provider, got)
    post = [s for s in seen if s[0] == "POST"][-1]
    if provider == "anthropic":
        assert post[2].get("x-api-key") == "k" and post[3]["system"] == "be brief" and post[3]["stream"] is True
    elif provider == "gemini":
        assert post[2].get("x-goog-api-key") == "k" and post[3]["systemInstruction"]["parts"][0]["text"] == "be brief" and "key=" not in post[1]
    elif provider == "ollama":
        assert "authorization" not in {k.lower() for k in post[2]} and post[3]["messages"][0]["role"] == "system"
    else:
        assert post[2].get("authorization") == "Bearer k" and post[3]["messages"][0]["content"] == "be brief"
try:
    run("openai", key="bad")
    raise SystemExit("a bad key must raise")
except a.ApiError as e:
    assert "401" in str(e) and "Incorrect API key" in str(e) and "bad" not in str(e).replace("Incorrect", ""), e
    print("error text:", e)
print(a.list_models({"provider": "openai", "key": "k", "base": root + "/v1"}), a.list_models({"provider": "gemini", "key": "k", "base": root + "/v1beta"}), a.list_models({"provider": "ollama", "base": root}))
print("piece_of:", repr(a.piece_of("openai", "data: [DONE]")), repr(a.piece_of("openai", ": ping")), repr(a.piece_of("anthropic", 'data: {"type":"ping"}')))

# the setup questions: the user picks from the service's own list, or types a model name - there is no built-in default
import builtins, getpass
a.appdata = None                                         # nothing is saved by this test
def scripted(answers, secret="sk-test"):
    queue = list(answers)
    builtins.input = lambda prompt="": queue.pop(0)
    getpass.getpass = lambda prompt="": secret
    return queue
queue = scripted(["6", root + "/v1", "yes", "", "99", "2"])       # custom address, keep key, blank and out-of-range answers are asked again, then number 2
config = a.setup({})
assert config["provider"] == "custom" and config["key"] == "sk-test" and config["model"] == "m-b", config
assert not queue, queue
queue = scripted(["5", "", "my-own-model"])                          # ollama lists llama3.2 on the fake server, but a typed name is accepted too
config = a.setup({})
assert config["provider"] == "ollama" and config["model"] == "my-own-model", config
a.PROVIDERS["openai"]["base"] = root + "/nolist"                   # a server that cannot list models: the user must type one
queue = scripted(["1", "yes", "", "gpt-x"])
config = a.setup({})
assert config["provider"] == "openai" and config["model"] == "gpt-x", config
assert all(p["model"] == "" for p in a.PROVIDERS.values()), "no service has a built-in model name"
print("setup questions ok")
print("all providers ok")
