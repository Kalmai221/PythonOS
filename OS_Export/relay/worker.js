// A tiny relay that turns a PythonOS problem report into a GitHub issue.
//
// Why a relay: a GitHub token inside an app can be extracted by anyone who opens the app. Here the token lives only in this
// Cloudflare Worker (as the secret GITHUB_TOKEN), and the app only knows the Worker's address.
//
// Deploy:  wrangler deploy  (see README.md)   Secrets:  GITHUB_TOKEN (fine-grained token, repo "Issues: write" only)
// Then in PythonOS:  settings set report_relay https://<your-worker>.workers.dev
const REPO = "Kalmai221/PythonOS";
const MAX_BODY = 20000;
const RATE = new Map(); // per-instance, best effort: one report per address per minute

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return json({ error: "POST a report" }, 405);
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    if (now - (RATE.get(ip) || 0) < 60000) return json({ error: "slow down: one report a minute" }, 429);
    let data;
    try { data = await request.json(); } catch { return json({ error: "bad JSON" }, 400); }
    const title = String(data.title || "Problem report").slice(0, 120);
    const body = String(data.body || "").slice(0, MAX_BODY);
    if (!body.trim()) return json({ error: "empty report" }, 400);
    RATE.set(ip, now);
    const response = await fetch(`https://api.github.com/repos/${REPO}/issues`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "pythonos-report-relay",
      },
      body: JSON.stringify({
        title: `[report] ${title}`,
        body: `${body}\n\n---\nSent from PythonOS ${String(data.version || "").slice(0, 40)} through the report relay.`,
        labels: ["user-report"],
      }),
    });
    if (!response.ok) return json({ error: "GitHub refused the report" }, 502);
    const issue = await response.json();
    return json({ url: issue.html_url });
  },
};

function json(value, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
}
