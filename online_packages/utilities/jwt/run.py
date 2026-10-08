#!/usr/bin/env python3
"""JWT decoder: read a JSON Web Token without sending it anywhere.

    jwt eyJhbGciOi...                       the header, the claims, and when it expires
    jwt eyJhbGciOi... --secret mysecret     also check an HS256, HS384 or HS512 signature with that secret
    cat token.txt | jwt                     the token can be piped in
Decoding only reads the token; it proves nothing unless you check the signature. A token is a password: do not paste real ones into other people's tools.
"""
import base64
import hashlib
import hmac
import json
import sys
import time

from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax

console = Console()
HASHES = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}
TIMES = (("iat", "Issued"), ("nbf", "Not before"), ("exp", "Expires"))


def b64(part):
    """Bytes from a base64url part (padding is optional in a token)."""
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def decode(token):
    """(header, claims, signing input, signature bytes). Raises ValueError with a sentence."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("A token has three parts separated by dots (header.claims.signature).")
    try:
        header = json.loads(b64(parts[0]))
        claims = json.loads(b64(parts[1]))
        signature = b64(parts[2]) if parts[2] else b""
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"The token is not valid base64 and JSON ({type(e).__name__}).") from None
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise ValueError("The header and the claims must be JSON objects.")
    return header, claims, (parts[0] + "." + parts[1]).encode("ascii"), signature


def check_signature(header, signing_input, signature, secret):
    """'valid', 'invalid' or a sentence saying why it cannot be checked."""
    algorithm = str(header.get("alg", ""))
    if algorithm not in HASHES:
        return f"cannot check a {algorithm or 'missing'} signature here (only HS256, HS384 and HS512 with a secret)"
    expected = hmac.new(secret.encode(), signing_input, HASHES[algorithm]).digest()
    return "valid" if hmac.compare_digest(expected, signature) else "invalid"


def when(value, now):
    """'2026-10-08 12:00:00 UTC (in 2 hours)' for a Unix time, or the value itself when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(value))
    except (OverflowError, OSError, ValueError):
        return str(value)
    delta = int(value - now)
    span = abs(delta)
    unit = f"{span // 86400} day(s)" if span >= 86400 else f"{span // 3600} hour(s)" if span >= 3600 else f"{span // 60} minute(s)" if span >= 60 else f"{span} second(s)"
    return f"{stamp} ({'in ' + unit if delta > 0 else unit + ' ago'})"


def status(claims, now):
    """Sentences about the time claims: expired, not yet valid, or fine."""
    notes = []
    if isinstance(claims.get("exp"), (int, float)) and claims["exp"] < now:
        notes.append("[red]expired[/red]")
    if isinstance(claims.get("nbf"), (int, float)) and claims["nbf"] > now:
        notes.append("[yellow]not valid yet[/yellow]")
    if "exp" not in claims:
        notes.append("[dim]no expiry[/dim]")
    return notes or ["[green]within its time limits[/green]"]


def main(argv):
    argv = list(argv)
    secret = None
    if "--secret" in argv:
        i = argv.index("--secret")
        if i + 1 >= len(argv):
            console.print(__doc__)
            return 1
        secret = argv[i + 1]
        del argv[i:i + 2]
    token = " ".join(argv) if argv else (sys.stdin.read() if not sys.stdin.isatty() else "")
    if not token.strip():
        console.print(__doc__)
        return 1
    try:
        header, claims, signing_input, signature = decode(token)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    now = time.time()
    console.print("[bold]Header[/bold]")
    console.print(Syntax(json.dumps(header, indent=2), "json", theme="ansi_dark", background_color="default"))
    console.print("[bold]Claims[/bold]")
    console.print(Syntax(json.dumps(claims, indent=2), "json", theme="ansi_dark", background_color="default"))
    for key, label in TIMES:
        if key in claims:
            console.print(f"{label:11} {escape(when(claims[key], now))}")
    console.print("Time        " + ", ".join(status(claims, now)))
    if str(header.get("alg", "")).lower() == "none":
        console.print("[bold red]alg is none: this token has no signature, anyone could have made it.[/bold red]")
    if secret is not None:
        result = check_signature(header, signing_input, signature, secret)
        colour = "green" if result == "valid" else "red" if result == "invalid" else "yellow"
        console.print(f"Signature   [{colour}]{escape(result)}[/{colour}]")
    else:
        console.print("[dim]Signature not checked (add --secret to check an HS256 token).[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
