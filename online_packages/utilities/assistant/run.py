#!/usr/bin/env python3
"""AI Assistant: chat with an AI model from the terminal. It asks which service you want to use (OpenAI, Anthropic, Google Gemini, OpenRouter,
Ollama on this computer, or any OpenAI-compatible address) and for your API key, then keeps the conversation going with the answer streaming in.

    assistant                      chat
    assistant "question"           ask one question and print the answer       (also: echo text | assistant "summarise this")
    assistant setup                choose the service, the model and the key again
    assistant forget               delete the saved key

Inside the chat:  /help  /models  /model <name>  /provider  /system <text>  /clear  /save [file]  /key  /forget  /exit
Your key is kept only in your own home folder (~/.config/assistant.json) and is sent only to the service you chose.
"""
import getpass
import json
import os
import sys

import requests

try:
    from pyos import appdata
except ImportError:                                                        # run on its own, outside PythonOS
    appdata = None

NAME = "assistant"
TIMEOUT = (15, 300)                          # connect, read (a long answer can take a while)
HISTORY_LIMIT = 40                           # messages kept in the conversation sent with each question

PROVIDERS = {
    "openai": {"title": "OpenAI", "base": "https://api.openai.com/v1", "kind": "openai", "key": True, "model": "",
               "hint": "Get a key at platform.openai.com/api-keys"},
    "anthropic": {"title": "Anthropic (Claude)", "base": "https://api.anthropic.com/v1", "kind": "anthropic", "key": True, "model": "",
                  "hint": "Get a key at console.anthropic.com/settings/keys"},
    "gemini": {"title": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta", "kind": "gemini", "key": True, "model": "",
               "hint": "Get a key at aistudio.google.com/apikey"},
    "openrouter": {"title": "OpenRouter (many models, one key)", "base": "https://openrouter.ai/api/v1", "kind": "openai", "key": True,
                   "model": "", "hint": "Get a key at openrouter.ai/keys"},
    "ollama": {"title": "Ollama (runs on this computer, no key)", "base": "http://localhost:11434", "kind": "ollama", "key": False, "model": "",
               "hint": "Install Ollama from ollama.com and pull a model first (for example: ollama pull llama3.2)"},
    "custom": {"title": "Another OpenAI-compatible address (Groq, Together, LM Studio, vLLM...)", "base": "", "kind": "openai", "key": True, "model": "",
               "hint": "You will be asked for the address, for example https://api.groq.com/openai/v1"},
}
ORDER = ["openai", "anthropic", "gemini", "openrouter", "ollama", "custom"]


# ------------------------------------------------------------------------------------------ saved settings
def load():
    data = appdata.load(NAME, {}) if appdata else {}
    return data if isinstance(data, dict) else {}


def save(config):
    if appdata is None:
        return
    appdata.save(NAME, config)
    try:
        os.chmod(appdata.path(NAME), 0o600)                               # the key is for this user only
    except (OSError, AttributeError):
        pass


# ------------------------------------------------------------------------------------------ talking to the services
class ApiError(Exception):
    pass


def headers_for(provider, key):
    kind = PROVIDERS[provider]["kind"]
    if kind == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    if kind == "gemini":
        return {"x-goog-api-key": key, "content-type": "application/json"}
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    if provider == "openrouter":
        headers["x-title"] = "PythonOS"
    return headers


def base_of(config):
    return (config.get("base") or PROVIDERS[config["provider"]]["base"]).rstrip("/")


def explain(response):
    """What the service said went wrong, in a line (never the key)."""
    try:
        data = response.json()
        message = (data.get("error") or {})
        message = message.get("message") if isinstance(message, dict) else message
        message = message or data.get("message") or str(data)[:200]
    except ValueError:
        message = response.text[:200]
    hints = {401: " - the key was refused: check it with /key", 403: " - this key may not use that model", 404: " - check the model name (/models)",
             429: " - too many requests or no credit left"}
    return f"{response.status_code}: {message}{hints.get(response.status_code, '')}"


def list_models(config):
    """The model names the service offers (best effort; an empty list when it cannot say)."""
    provider, key = config["provider"], config.get("key", "")
    kind = PROVIDERS[provider]["kind"]
    base = base_of(config)
    try:
        if kind == "ollama":
            r = requests.get(f"{base}/api/tags", timeout=TIMEOUT[0])
            return [m["name"] for m in r.json().get("models", [])] if r.ok else []
        if kind == "gemini":
            r = requests.get(f"{base}/models", headers=headers_for(provider, key), timeout=TIMEOUT[0])
            return [m["name"].split("/", 1)[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])] if r.ok else []
        r = requests.get(f"{base}/models", headers=headers_for(provider, key), timeout=TIMEOUT[0])
        if not r.ok:
            return []
        items = r.json().get("data", [])
        return sorted(m["id"] for m in items if isinstance(m, dict) and "id" in m)
    except (requests.RequestException, ValueError, KeyError):
        return []


def lines_of(response):
    """The decoded lines of a streaming answer."""
    for raw in response.iter_lines(decode_unicode=False):
        if raw:
            yield raw.decode("utf-8", "replace")


def stream_answer(config, messages, system):
    """Send the conversation; yield the answer's text in pieces as it arrives. Raises ApiError with a readable reason."""
    provider, key, model = config["provider"], config.get("key", ""), config["model"]
    kind = PROVIDERS[provider]["kind"]
    base = base_of(config)
    try:
        if kind == "anthropic":
            body = {"model": model, "max_tokens": 4096, "stream": True, "messages": messages}
            if system:
                body["system"] = system
            response = requests.post(f"{base}/messages", headers=headers_for(provider, key), json=body, stream=True, timeout=TIMEOUT)
        elif kind == "gemini":
            body = {"contents": [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages]}
            if system:
                body["systemInstruction"] = {"parts": [{"text": system}]}
            response = requests.post(f"{base}/models/{model}:streamGenerateContent?alt=sse", headers=headers_for(provider, key), json=body, stream=True, timeout=TIMEOUT)
        elif kind == "ollama":
            body = {"model": model, "messages": ([{"role": "system", "content": system}] if system else []) + messages, "stream": True}
            response = requests.post(f"{base}/api/chat", json=body, stream=True, timeout=TIMEOUT)
        else:
            body = {"model": model, "stream": True, "messages": ([{"role": "system", "content": system}] if system else []) + messages}
            response = requests.post(f"{base}/chat/completions", headers=headers_for(provider, key), json=body, stream=True, timeout=TIMEOUT)
    except requests.ConnectionError:
        raise ApiError("could not connect" + (" - is Ollama running?" if kind == "ollama" else " - check your internet connection"))
    except requests.RequestException as e:
        raise ApiError(type(e).__name__)
    if not response.ok:
        raise ApiError(explain(response))
    for line in lines_of(response):
        text = piece_of(kind, line)
        if text:
            yield text


def piece_of(kind, line):
    """The text in one line of a streaming answer ('' when the line carries none)."""
    if kind == "ollama":
        try:
            return json.loads(line).get("message", {}).get("content", "")
        except ValueError:
            return ""
    if not line.startswith("data:"):
        return ""
    data = line[5:].strip()
    if data == "[DONE]" or not data:
        return ""
    try:
        item = json.loads(data)
    except ValueError:
        return ""
    if kind == "anthropic":
        delta = item.get("delta") or {}
        return delta.get("text", "") if item.get("type") == "content_block_delta" else ""
    if kind == "gemini":
        parts = ((item.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)
    choices = item.get("choices") or [{}]
    return (choices[0].get("delta") or {}).get("content") or ""


# ------------------------------------------------------------------------------------------ setup
def ask_number(prompt, count, default=1):
    while True:
        answer = input(f"{prompt} [{default}]: ").strip() or str(default)
        if answer.isdigit() and 1 <= int(answer) <= count:
            return int(answer)
        print("Type one of the numbers.")


def setup(config=None):
    """Ask which service, the address if needed, the key and the model. Returns the new config."""
    config = dict(config or {})
    print("\nWhich AI service do you want to use?")
    for number, name in enumerate(ORDER, 1):
        print(f"  {number}) {PROVIDERS[name]['title']}")
    current = ORDER.index(config["provider"]) + 1 if config.get("provider") in ORDER else 1
    provider = ORDER[ask_number("Number", len(ORDER), current) - 1]
    info = PROVIDERS[provider]
    config = {"provider": provider, "model": info["model"], "system": config.get("system", ""), "save_key": config.get("save_key", True)}
    print(info["hint"])
    if provider == "custom":
        config["base"] = input("Address (ends with /v1 or similar): ").strip().rstrip("/")
        if not config["base"].startswith(("http://", "https://")):
            print("The address must start with http:// or https://")
            return setup(config)
    if info["key"]:
        key = getpass.getpass("API key (hidden as you type; Enter to skip if the service needs none): ").strip()
        config["key"] = key
        if key:
            config["save_key"] = input("Keep the key on this computer so you are not asked again? (yes/no) [yes]: ").strip().lower() not in ("n", "no")
    models = list_models(config)
    if models:
        shown = models[:40]
        print("\nModels this service offers" + (f" (first {len(shown)} of {len(models)})" if len(models) > len(shown) else "") + ":")
        for number, name in enumerate(shown, 1):
            print(f"  {number}) {name}")
        prompt = "Number from the list, or type a model name: "
    else:
        print("\nThe list of models could not be loaded (the key may be wrong, or the service does not say).")
        prompt = "Type the model name: "
    while True:
        pick = input(prompt).strip()
        if models and pick.isdigit() and 1 <= int(pick) <= len(models[:40]):
            config["model"] = models[int(pick) - 1]
            break
        if pick and not pick.isdigit():
            config["model"] = pick
            break
        print("Choose a number from the list, or type the name of a model.")
    stored = dict(config)
    if not config.get("save_key", True):
        stored.pop("key", None)
    save(stored)
    print(f"\nReady: {info['title']}, model {config['model']}.")
    return config


# ------------------------------------------------------------------------------------------ chat
def say_answer(config, messages, system):
    """Print the answer as it streams in and return it (None if it failed)."""
    text = []
    try:
        for piece in stream_answer(config, messages[-HISTORY_LIMIT:], system):
            sys.stdout.write(piece)
            sys.stdout.flush()
            text.append(piece)
    except ApiError as e:
        print(f"\n[the service said] {e}")
        return None
    except KeyboardInterrupt:
        print("\n[stopped]")
    print()
    return "".join(text)


def help_text():
    return ("  /models            list the models this key can use\n  /model <name>      use another model\n  /provider          change service, key or model (setup)\n"
            "  /system <text>     tell the assistant how to behave (empty to clear)\n  /clear             forget this conversation\n"
            "  /save [file]       save the conversation as a text file in your home folder\n  /key               enter the key again\n"
            "  /forget            delete the saved key\n  /exit              leave\n  A line ending with \\ continues on the next line.")


def read_prompt():
    line = input("\nyou> ")
    while line.endswith("\\"):
        line = line[:-1] + "\n" + input("...> ")
    return line.strip()


def chat(config):
    info = PROVIDERS[config["provider"]]
    print(f"AI Assistant - {info['title']}, model {config['model']}. Type /help for commands, /exit to leave.")
    messages, system = [], config.get("system", "")
    while True:
        try:
            line = read_prompt()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line.startswith("/"):
            command, _space, rest = line[1:].partition(" ")
            rest = rest.strip()
            if command in ("exit", "quit", "q"):
                return
            if command == "help":
                print(help_text())
            elif command == "models":
                names = list_models(config)
                print("\n".join(f"  {n}" for n in names[:60]) if names else "Could not list the models.")
            elif command == "model" and rest:
                config["model"] = rest
                save({k: v for k, v in config.items() if k != "key" or config.get("save_key", True)})
                print(f"Now using {rest}.")
            elif command == "provider":
                config = setup(config)
                info = PROVIDERS[config["provider"]]
            elif command == "system":
                system = rest
                config["system"] = system
                save({k: v for k, v in config.items() if k != "key" or config.get("save_key", True)})
                print("Instructions set." if system else "Instructions cleared.")
            elif command == "clear":
                messages = []
                print("Conversation cleared.")
            elif command == "save":
                path = rest or "assistant-chat.txt"
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        for m in messages:
                            f.write(("You: " if m["role"] == "user" else "Assistant: ") + m["content"] + "\n\n")
                    print(f"Saved to {path}")
                except OSError as e:
                    print(f"Could not save: {e}")
            elif command == "key":
                config["key"] = getpass.getpass("New API key: ").strip()
                save({k: v for k, v in config.items() if k != "key" or config.get("save_key", True)})
                print("Key updated.")
            elif command == "forget":
                config.pop("key", None)
                save({k: v for k, v in config.items() if k != "key"})
                print("The saved key was deleted. You will be asked for it next time.")
            else:
                print("Unknown command. /help lists them.")
            continue
        messages.append({"role": "user", "content": line})
        print()
        answer = say_answer(config, messages, system)
        if answer is None:
            messages.pop()
        else:
            messages.append({"role": "assistant", "content": answer})


def ready_config():
    """The saved config, set up (and the key asked for) when something is missing."""
    config = load()
    if config.get("provider") not in PROVIDERS or not config.get("model"):
        return setup(config)
    if PROVIDERS[config["provider"]]["key"] and not config.get("key"):
        key = getpass.getpass(f"API key for {PROVIDERS[config['provider']]['title']} (hidden; not saved): ").strip()
        if not key:
            print("A key is needed for this service. Run: assistant setup")
            return None
        config["key"] = key
    return config


def execute(args=None):
    args = list(args or [])
    try:
        if args and args[0] == "setup":
            setup(load())
            return True
        if args and args[0] == "forget":
            config = load()
            config.pop("key", None)
            save(config)
            print("The saved key was deleted.")
            return True
        config = ready_config()
        if config is None:
            return False
        question = " ".join(args).strip()
        if not sys.stdin.isatty() and question != "":
            piped = sys.stdin.read().strip()
            question = f"{question}\n\n{piped}" if piped else question
        if question:
            answer = say_answer(config, [{"role": "user", "content": question}], config.get("system", ""))
            return answer is not None
        chat(config)
        return True
    except (KeyboardInterrupt, EOFError):
        print()
        return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
