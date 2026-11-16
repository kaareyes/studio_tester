"""The report of one run: a single HTML file next to its screenshots (opens in any browser, can be printed to PDF)."""
import html

COLORS = {"passed": "#2e8b57", "failed": "#c0392b", "skipped": "#b9770e", "running": "#2f6fb0", "waiting": "#888888"}


def write_html(state, path):
    counts = state["counts"]
    rows = []
    for index, result in enumerate(state["results"], 1):
        shot = " ".join(f'<a href="{html.escape(f)}">{html.escape(f.split("_", 2)[-1])}</a>' for f in result.get("files", []))
        rows.append(
            f'<tr><td>{index}</td><td>{html.escape(result["name"])}</td>'
            f'<td><b style="color:{COLORS.get(result["status"], "#000")}">{result["status"].upper()}</b></td>'
            f'<td>{result["seconds"]} s</td><td>{html.escape(result["message"])} {shot}</td></tr>')
    verdict = "FAILED" if counts["failed"] else ("PASSED" if counts["passed"] else "NOTHING RAN")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Studio Tester report</title>
<style>body{{font-family:-apple-system,Helvetica,Arial,sans-serif;margin:32px;color:#1f3a5f}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #c5d0dc;padding:6px 8px;text-align:left;font-size:13px;vertical-align:top}}
th{{background:#eef3f9}}.big{{font-size:22px;font-weight:700}}</style></head><body>
<h1>Studio Tester report</h1>
<p class="big" style="color:{COLORS['failed'] if counts['failed'] else COLORS['passed']}">{verdict}</p>
<p><b>Suite:</b> {html.escape(state['suite'])} &nbsp; <b>Started:</b> {state['started']} &nbsp; <b>Finished:</b> {state['finished'] or '-'}<br>
<b>Studio build:</b> {html.escape(state['build'])}<br>
<b>Camera:</b> {html.escape(state['camera'] or 'none')} ({html.escape(state['camera_reason'])})<br>
<b>Options:</b> {html.escape(', '.join(f'{k}: {v}' for k, v in (state.get('options') or {}).items() if str(v).strip()) or 'none (random)')}<br>
<b>Passed:</b> {counts['passed']} &nbsp; <b>Failed:</b> {counts['failed']} &nbsp; <b>Skipped:</b> {counts['skipped']}</p>
<table><tr><th>#</th><th>Test</th><th>Result</th><th>Time</th><th>Details</th></tr>{''.join(rows)}</table>
<p><a href="run.log">run.log</a> (every step with the time) &nbsp; <a href="results.json">results.json</a> &nbsp; <a href="studio_console.log">studio_console.log</a> (if the test started Studio)</p><h3>Log</h3><pre>{html.escape(chr(10).join(state['log']))}</pre></body></html>"""
    with open(path, "w") as handle:
        handle.write(page)
