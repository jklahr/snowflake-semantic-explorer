#!/usr/bin/env python3
"""Self-check for the snapshot builder and the inline-ask dialog. Needs: python3, and playwright with chromium (the browser part is skipped if missing).
   python3 semantic-dashboard/tests/test_inline_ask.py"""
import json, subprocess, sys, tempfile, pathlib
HERE = pathlib.Path(__file__).resolve().parent
BUILD = HERE.parent / "scripts" / "build_snapshot.py"
fixture = HERE / "fixture" / "spec.json"
out = pathlib.Path(tempfile.mkdtemp()) / "fixture.html"

def build(spec):
    return subprocess.run([sys.executable, str(BUILD), "--spec", str(spec), "--out", str(out)], capture_output=True, text=True)

r = build(fixture)
assert r.returncode == 0, r.stderr
# builder preview must honour the default end date (Feb), not the partial last month (Mar)
assert "in 2026-02" in r.stdout and "2026-03" not in r.stdout.split("preview")[1], r.stdout
bad = json.loads(fixture.read_text()); bad["catalog"]["metrics"][0].pop("view")
tmp = pathlib.Path(tempfile.mkdtemp()) / "spec.json"; (pathlib.Path(tmp.parent) / "data.json").write_text((HERE / "fixture" / "data.json").read_text()); tmp.write_text(json.dumps(bad))
r2 = build(tmp); assert r2.returncode != 0 and "needs a 'view'" in r2.stderr, r2.stderr
print("builder checks passed")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed: skipped the browser checks"); sys.exit(0)

MOCK = """window.__calls=[]; window.__mode='ok';
window.claude={use:async n=>n==='mcp'?{callTool:async(s,t,i,o)=>{window.__calls.push({s,t,i});
 if(window.__mode==='err') throw {code:'server_not_connected',message:'x'};
 const P={answer:'**ok** answer\\n\\n| a | b |\\n|---|---|\\n| 1 | 2 |',rows:{columns:['C'],data:[['1']]},sql:'SELECT 1'};
 return {content:[{type:'text',text:JSON.stringify(P)}],payload:P};}}:null};"""
with sync_playwright() as p:
    b = p.chromium.launch()
    def page(mock):
        pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        if mock: pg.add_init_script(MOCK)
        pg.goto(out.as_uri()); pg.wait_for_timeout(600); return pg, errs
    open_ = lambda pg: (pg.click("section.tile.kpi [aria-label='Explain this data with Claude']"), pg.wait_for_selector(".modal"))
    pg, errs = page(False); open_(pg)
    names = pg.eval_on_selector_all(".modal button", "e=>e.map(x=>x.innerText.trim())")
    assert "Ask Snowflake" not in names and "Ask Claude" in names and not errs, names
    pg, errs = page(True); open_(pg)
    pg.click(".modal button:has-text('Ask Snowflake')"); pg.wait_for_selector(".ask-out table")
    c = pg.evaluate("window.__calls[0]")
    assert c["s"] == "fixture_connector" and c["t"] == "ask_semantic_view" and c["i"]["VIEW_NAME"] == "V1" and c["i"]["DB_NAME"] == "DB" and c["i"]["SCHEMA_NAME"] == "SCH", c
    assert "2026-01" in c["i"]["QUESTION"], c["i"]["QUESTION"]
    assert "ok" in pg.inner_text(".ask-out") and not errs
    pg.evaluate("window.__mode='err'; document.querySelector('.overlay').remove()"); open_(pg)
    pg.click(".modal button:has-text('Ask Snowflake')"); pg.wait_for_selector(".ask-out .bad")
    assert "not connected" in pg.inner_text(".ask-out .bad")
    b.close()
print("browser checks passed")
