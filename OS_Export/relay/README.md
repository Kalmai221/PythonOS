# Report relay

Optional. Lets `report` file a GitHub issue for the user in one step, without putting a GitHub token inside PythonOS.

Without a relay, `report` still works: the user reads the report, then opens a prefilled issue link or saves a file. Nothing is
ever sent unless the user chooses it.

## Set it up (about five minutes, free)

1. Create a **fine-grained GitHub token** for the PythonOS repository with only **Issues: Read and write**.
2. `npm create cloudflare@latest` (or use the dashboard) and paste [`worker.js`](worker.js) as the Worker.
3. Add the token as a secret named `GITHUB_TOKEN` (`wrangler secret put GITHUB_TOKEN`).
4. Deploy. You get an address like `https://pythonos-reports.<you>.workers.dev`.
5. In PythonOS: `settings set report_relay https://pythonos-reports.<you>.workers.dev`
   (ship it as a default by changing `report_relay` in `pyos/settings.py` if you want every install to use it).

## What it does and does not do

* Accepts `POST` JSON `{title, body, version}`, creates an issue labelled `user-report`, answers `{url}`.
* Limits the size and allows one report per address per minute (best effort).
* The app redacts user names, home folders, email and IP addresses **before** anything leaves the device, and always shows the user
  the full text first. The relay stores nothing.
* Anyone who knows the address can post an issue, so treat the token as limited to Issues, and moderate like any public tracker.
