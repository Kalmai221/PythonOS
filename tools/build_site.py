#!/usr/bin/env python3
"""Build the website: site_src/ (page bodies with a small header) + the shared header, footer and documentation sidebar -> site/.

    python tools/build_site.py            write the pages into site/
    python tools/build_site.py --check    fail if site/ is not what the sources produce (CI runs this)

A page in site_src/ starts with an HTML comment of "key: value" lines:
    title        the page title (shown after "PythonOS - " in the tab)
    description  one sentence for search engines and link previews
    nav          which header link is current: download, docs, apps, status (or empty)
    section      "docs" puts the page in the documentation layout (a sidebar, the page in a column, previous and next links)
    group, order where the page sits in the documentation sidebar
    scripts      comma-separated scripts in site/ to load after app.js
Links inside pages use {{root}} so they work from site/ and from site/docs/.
The command reference (docs/commands.html) is not a source file: it is made here from the manual of PythonOS itself (pyos/manpages.py).
"""
import html
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
SRC = os.path.join(ROOT, "site_src")
OUT = os.path.join(ROOT, "site")
REPO = "https://github.com/Kalmai221/PythonOS"

NAV = [("download", "Download", "download.html"), ("docs", "Documentation", "docs/index.html"), ("apps", "Apps", "apps.html"), ("status", "Build status", "status.html")]
DOC_GROUPS = ["Using PythonOS", "Building apps", "Contributing"]

LAYOUT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="theme-color" content="#faf9f6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#131312" media="(prefers-color-scheme: dark)">
<script>try {{ var t = localStorage.getItem("theme"); if (t) document.documentElement.setAttribute("data-theme", t); }} catch (e) {{}}</script>
<link rel="stylesheet" href="{root}style.css?v=7">
<script src="{root}app.js?v=4" defer></script>
{scripts}</head>
<body>
<a class="skip" href="#main">Skip to the content</a>
<header class="bar">
  <div class="wrap">
    <a class="brand" href="{root}index.html"><span class="logo" aria-hidden="true">&gt;_</span>PythonOS</a>
    <nav aria-label="Main">
{nav}
      <a class="opt" href="{repo}">GitHub</a>
      <button class="icon-btn" id="theme" type="button" aria-pressed="false" aria-label="Switch theme">
        <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
    </nav>
  </div>
</header>

{content}

<footer>
  <div class="wrap">
    <span>PythonOS is open source. <a href="{repo}">Source</a> · <a href="{repo}/issues">Report a problem</a> · <a href="{root}docs/contributing.html">Contribute</a></span>
    <span>Update from inside PythonOS with <code>updatecheck</code></span>
  </div>
</footer>
</body>
</html>
"""


def parse(path):
    """(meta dict, body) of a source page."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    match = re.match(r"\s*<!--(.*?)-->\s*", text, re.S)
    if not match:
        raise SystemExit(f"{path}: the page must start with a <!-- title: ... --> comment")
    meta = {}
    for line in match.group(1).strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    if not meta.get("title") or not meta.get("description"):
        raise SystemExit(f"{path}: the comment needs title and description")
    return meta, text[match.end():]


def esc(text):
    return html.escape(str(text), quote=True)


def _pair(item):
    """(text, note) from a manual entry that may be a bare string or a longer tuple."""
    if isinstance(item, str):
        return item, ""
    return item[0], (item[1] if len(item) > 1 else "")


def commands_page():
    """(meta, body) of the command reference, made from the manual."""
    sys.path.insert(0, ROOT)
    os.environ.setdefault("PYOS_BUNDLED", "1")
    from pyos import helpview, manpages
    pages = manpages.PAGES
    commands = {f[:-3] for f in os.listdir(os.path.join(ROOT, "commands")) if f.endswith(".py")}
    groups = {}
    for name in sorted(commands):
        groups.setdefault(helpview.category_of(name), []).append(name)
    order = list(helpview.CATEGORIES) + ["Other"]
    topics = sorted(n for n in pages if n not in commands and pages[n].get("description"))

    def link(name):
        return f'<a href="#cmd-{esc(name)}"><code>{esc(name)}</code></a>' if name in pages else f"<code>{esc(name)}</code>"

    def entry(name):
        page = pages.get(name)
        if not page:
            return f'<section class="cmd" id="cmd-{esc(name)}"><h3>{esc(name)}</h3></section>\n'
        out = [f'<section class="cmd" id="cmd-{esc(name)}" data-name="{esc(name)}">', f'<h3>{esc(name)}</h3>', f'<p class="summary">{esc(page["summary"])}</p>']
        if page.get("synopsis"):
            out.append("<pre><code>" + "\n".join(esc(s) for s in page["synopsis"]) + "</code></pre>")
        out.append(f'<p>{esc(page["description"])}</p>')
        if page.get("options"):
            out.append('<div class="table-wrap"><table><tbody>' + "".join(f'<tr><td><code>{esc(o)}</code></td><td>{esc(d)}</td></tr>' for o, d in (_pair(x) for x in page["options"])) + "</tbody></table></div>")
        if page.get("examples"):
            out.append("<pre><code>" + "\n".join(f'<span class="g">$</span> {esc(e)}' + (f'  <span class="d"># {esc(n)}</span>' if n else "") for e, n in (_pair(x) for x in page["examples"])) + "</code></pre>")
        if page.get("see"):
            out.append('<p class="muted">See also: ' + ", ".join(link(s) for s in page["see"]) + ".</p>")
        out.append("</section>")
        return "\n".join(out) + "\n"

    parts = ['<h1>Command reference</h1>',
             '<p class="lead">Every command in PythonOS, from the manual that ships with it. Inside PythonOS the same text is <code>man &lt;command&gt;</code>, and <code>help</code> lists the groups.</p>',
             '<p><label class="sr" for="cmd-filter">Filter the commands</label><input id="cmd-filter" type="search" placeholder="Filter by name or description" autocomplete="off" '
             'style="width:100%;max-width:26em;font:inherit;padding:8px 10px;border-radius:6px;border:1px solid var(--line-strong);background:var(--surface);color:var(--text)"></p>',
             '<p class="muted">Groups: ' + ", ".join(f'<a href="#group-{esc(g.lower().replace(" ", "-"))}">{esc(g)}</a>' for g in order if g in groups) + (', <a href="#topics">Topics</a>' if topics else "") + ".</p>"]
    for group in order:
        if group not in groups:
            continue
        blurb = helpview.CATEGORIES.get(group, ("Commands that are not in a group yet",))[0]
        parts.append(f'<h2 id="group-{esc(group.lower().replace(" ", "-"))}">{esc(group)}</h2><p class="muted">{esc(blurb)}</p>')
        parts += [entry(n) for n in groups[group]]
    if topics:
        parts.append('<h2 id="topics">Topics</h2><p class="muted">Longer explanations in the manual (<code>man &lt;topic&gt;</code>).</p>')
        parts += [entry(n) for n in topics]
    parts.append("""<script>
(function () {
  var box = document.getElementById("cmd-filter");
  if (!box) return;
  box.addEventListener("input", function () {
    var q = box.value.trim().toLowerCase();
    document.querySelectorAll(".cmd[data-name]").forEach(function (el) { el.hidden = !!q && el.textContent.toLowerCase().indexOf(q) < 0; });
  });
})();
</script>""")
    meta = {"title": "Command reference", "description": "Every PythonOS command with usage, options and examples.", "nav": "docs", "section": "docs", "group": "Using PythonOS", "order": "30"}
    return meta, "\n".join(parts)


def collect():
    """[(relative output path, meta, body)] for every page."""
    pages = []
    for base, _dirs, files in os.walk(SRC):
        for name in sorted(files):
            if name.endswith(".html") and not name.startswith("_"):
                full = os.path.join(base, name)
                meta, body = parse(full)
                pages.append((os.path.relpath(full, SRC).replace(os.sep, "/"), meta, body))
    meta, body = commands_page()
    pages.append(("docs/commands.html", meta, body))
    return pages


def render(pages):
    docs = [(p, m) for p, m, _b in pages if m.get("section") == "docs"]
    docs.sort(key=lambda pm: (DOC_GROUPS.index(pm[1].get("group", DOC_GROUPS[0])) if pm[1].get("group", DOC_GROUPS[0]) in DOC_GROUPS else 99, int(pm[1].get("order", 50)), pm[0]))
    results = {}
    for path, meta, body in pages:
        depth = path.count("/")
        root = "../" * depth
        nav = "\n".join(f'      <a href="{root}{href}"' + (' aria-current="page"' if meta.get("nav") == key else "") + f">{label}</a>" for key, label, href in NAV)
        scripts = "".join(f'<script src="{root}{s.strip()}" defer></script>\n' for s in meta.get("scripts", "").split(",") if s.strip())
        content = body.replace("{{root}}", root)
        if meta.get("section") == "docs":
            side, last_group = [], None
            for p, m in docs:
                if m.get("group") != last_group:
                    if last_group is not None:
                        side.append("</ul>")
                    side.append(f"<h4>{esc(m.get('group', ''))}</h4><ul>")
                    last_group = m.get("group")
                href = os.path.relpath(p, os.path.dirname(path) or ".").replace(os.sep, "/")
                side.append(f'<li><a href="{href}"' + (' aria-current="page"' if p == path else "") + f">{esc(m['title'])}</a></li>")
            side.append("</ul>")
            names = [p for p, _m in docs]
            at = names.index(path)
            def pager(i, label):
                if not 0 <= i < len(names):
                    return "<span></span>"
                target = os.path.relpath(names[i], os.path.dirname(path) or ".").replace(os.sep, "/")
                return f'<a href="{target}">{label}</a>'
            titles = dict((p, m["title"]) for p, m in docs)
            prev_next = ('<nav class="page-nav" aria-label="Pages">' + pager(at - 1, "&larr; " + esc(titles[names[at - 1]]) if at > 0 else "") +
                         pager(at + 1, esc(titles[names[at + 1]]) + " &rarr;" if at + 1 < len(names) else "") + "</nav>")
            content = ('<div class="wrap docs">\n<nav class="docs-nav" aria-label="Documentation">' + "".join(side) + '</nav>\n<main id="main" class="doc">\n' +
                       content.strip() + "\n" + prev_next + "\n</main>\n</div>")
        else:
            content = content.strip()
            if not content.lstrip().startswith("<main"):
                content = '<main id="main">\n' + content + "\n</main>"
        results[path] = LAYOUT.format(title=esc("PythonOS - " + meta["title"] if path != "index.html" else "PythonOS - a terminal operating system written in Python"),
                                      description=esc(meta["description"]), root=root, scripts=scripts, nav=nav, content=content, repo=REPO)
    return results


def main():
    check = "--check" in sys.argv
    results = render(collect())
    problems = []
    for path, text in sorted(results.items()):
        target = os.path.join(OUT, path.replace("/", os.sep))
        current = None
        if os.path.exists(target):
            with open(target, encoding="utf-8", newline="") as f:
                current = f.read().replace("\r\n", "\n")
        if current != text:
            if check:
                problems.append(path)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
    if check:
        if problems:
            print("The website is not up to date with site_src/ (run: python tools/build_site.py). Stale: " + ", ".join(problems))
            return 1
        print(f"Website is current ({len(results)} pages).")
        return 0
    print(f"Built {len(results)} pages into site/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
