#!/usr/bin/env python3
"""Build a self-contained, interactive dashboard file from a spec and query results.

    python build_snapshot.py --spec spec.json --out dashboard.html
    python build_snapshot.py --spec spec.json --ops ops.json --out dashboard.html     # apply edits, rebuild

Python 3.9+, standard library only. See references/snapshot-format.md for the formats.

What it guards against (each is an error, never a silent fix):
  * unknown metric/dimension names, tiles that no dataset can answer
  * ragged rows, non-numeric metric values, duplicated dimension combinations (a pasted chunk twice)
  * totals that do not match an independent ungrouped query (``reconcile``): catches dropped or
    mistyped rows when results were copied by hand
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "explorer.template.html"
MAX_ROWS = 50_000
MAX_BYTES = 20 * 1024 * 1024
PLAN_WORDS = ("BUDGET", "PLAN", "TARGET", "FORECAST", "QUOTA")
TILE_TYPES = {"kpi", "line", "bar", "hbar", "table"}
POPS = {"none", "DoD", "WoW", "MoM", "QoQ", "YoY"}
POP_BY_GRAIN = {"day": "DoD", "week": "WoW", "month": "MoM", "period": "MoM", "quarter": "QoQ"}
FILTER_OPS = {"in", "not_in", "eq", "ne", "lt", "lte", "gt", "gte", "between", "contains", "starts_with"}
SINGLE_OPS = {"eq", "ne", "lt", "lte", "gt", "gte", "contains", "starts_with"}


class SpecError(Exception):
    """A problem the author of the spec can fix; the message says how."""


def fail(msg: str) -> None:
    raise SpecError(msg)


# --------------------------------------------------------------------------- loading
def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"file not found: {path}")
    except json.JSONDecodeError as e:
        fail(f"{path.name} is not valid JSON ({e.msg} at line {e.lineno}, column {e.colno})")


def to_number(v: Any, where: str) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        fail(f"{where}: true/false is not a number")
    if isinstance(v, (int, float, Decimal)):
        if v != v or v in (float("inf"), float("-inf")):
            fail(f"{where}: NaN or infinity is not allowed")
        return round(float(v), 2)
    if isinstance(v, str):
        try:
            return round(float(v.replace(",", "")), 2)
        except ValueError:
            pass
    fail(f"{where}: {v!r} is not a number")


def to_dim(v: Any) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        return "(blank)"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))                      # 2026.0 -> "2026"
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return str(v)


def read_chunk(path: Path) -> tuple[list[str], list[list[Any]]]:
    """A data file is {"columns": [...], "data": [[...]]} or {"rows": [{...}]} or a bare list of objects.
    A query result copied whole (with "rows") works as is."""
    raw = load_json(path)
    if isinstance(raw, list):
        raw = {"rows": raw}
    if not isinstance(raw, dict):
        fail(f"{path.name}: expected an object with 'columns' and 'data', or 'rows'")
    if "rows" in raw and isinstance(raw["rows"], list):
        rows = raw["rows"]
        if not rows:
            return list(raw.get("columns", [])), []
        if not all(isinstance(r, dict) for r in rows):
            fail(f"{path.name}: 'rows' must be a list of objects")
        cols = list(raw.get("columns") or rows[0].keys())
        return cols, [[r.get(c) for c in cols] for r in rows]
    if "columns" in raw and "data" in raw:
        return list(raw["columns"]), [list(r) for r in raw["data"]]
    fail(f"{path.name}: expected 'columns' with 'data', or 'rows'")


def resolve_datasets(spec: dict[str, Any], base: Path) -> list[dict[str, Any]]:
    cat_m = {m["name"]: m for m in spec["catalog"]["metrics"]}
    cat_d = {d["name"] for d in spec["catalog"]["dimensions"]}
    out, total = [], 0
    ids: set[str] = set()
    for ds in spec.get("datasets") or []:
        did = ds.get("id") or fail("every dataset needs an 'id'")
        if did in ids:
            fail(f"duplicate dataset id '{did}'")
        ids.add(did)
        dims, mets = list(ds.get("dimensions", [])), list(ds.get("metrics", []))
        if not mets:
            fail(f"dataset '{did}' lists no metrics")
        for d in dims:
            if d not in cat_d:
                fail(f"dataset '{did}': dimension '{d}' is not in catalog.dimensions")
        for m in mets:
            if m not in cat_m:
                fail(f"dataset '{did}': metric '{m}' is not in catalog.metrics")
            if cat_m[m].get("num") or cat_m[m].get("den"):
                fail(f"dataset '{did}': '{m}' is a ratio (num/den). Put its numerator '{cat_m[m].get('num')}' and "
                     f"denominator '{cat_m[m].get('den')}' in the dataset instead; the page computes the ratio.")
        want = dims + mets
        chunks: list[tuple[str, list[str], list[list[Any]]]] = []
        for f in ds.get("files", []):
            cols, data = read_chunk(base / f)
            chunks.append((f, cols, data))
        if ds.get("rows_compact"):
            rc = ds["rows_compact"]
            chunks.append(("rows_compact", list(rc["columns"]), [list(r) for r in rc["data"]]))
        if not chunks:
            fail(f"dataset '{did}' has no 'files' or 'rows_compact'")
        rows: list[list[Any]] = []
        for name, cols, data in chunks:
            if not data:
                continue                                                # an empty chunk adds nothing; "no rows" is reported below
            lower = {c.upper(): i for i, c in enumerate(cols)}          # warehouse column names are upper case
            missing = [c for c in want if c.upper() not in lower]
            if missing:
                fail(f"dataset '{did}', {name}: missing columns {missing} (found {cols})")
            idx = [lower[c.upper()] for c in want]
            for n, r in enumerate(data, 1):
                if len(r) != len(cols):
                    fail(f"dataset '{did}', {name}, row {n}: has {len(r)} values but {len(cols)} columns")
                rows.append([to_dim(r[i]) for i in idx[: len(dims)]] +
                            [to_number(r[i], f"dataset '{did}', {name}, row {n}, {want[k + len(dims)]}") for k, i in enumerate(idx[len(dims):])])
        if not rows:
            fail(f"dataset '{did}' has no rows. Check the query returned data and the files are listed.")
        if dims:
            seen: dict[tuple, int] = {}
            for n, r in enumerate(rows, 1):
                k = tuple(r[: len(dims)])
                if k in seen:
                    fail(f"dataset '{did}': rows {seen[k]} and {n} share the same {dims} = {list(k)}. "
                         f"Usually a chunk was included twice or the query grouped by fewer dimensions than listed.")
                seen[k] = n
        elif len(rows) > 1:
            fail(f"dataset '{did}' has no dimensions, so it must be exactly one row (got {len(rows)})")
        total += len(rows)
        sql = ds.get("sql") or ""
        if not isinstance(sql, str):
            fail(f"dataset '{did}': 'sql' must be the statement text returned by the query tool")
        out.append({"id": did, "dimensions": dims, "metrics": mets, "columns": want, "rows": rows,
                    "partial": bool(ds.get("partial")), "note": ds.get("note") or "", "sql": sql.strip()[:4000]})
    if not out:
        fail("the spec has no datasets. Add at least one query result.")
    if total > MAX_ROWS:
        fail(f"{total:,} rows is more than the {MAX_ROWS:,} limit. Use a coarser dimension or a shorter period range.")
    return out


# --------------------------------------------------------------------------- spec checks
def check_catalog(spec: dict[str, Any]) -> None:
    for k in ("title", "view", "catalog"):
        if not spec.get(k):
            fail(f"spec is missing '{k}'")
    cat = spec["catalog"]
    names = set()
    for m in cat.get("metrics", []):
        n = m.get("name") or fail("a catalog metric has no name")
        if n in names:
            fail(f"duplicate metric '{n}' in catalog")
        names.add(n)
        m.setdefault("label", n.replace("_", " ").title())
        if m.get("format") not in ("currency", "percent", "number", None):
            fail(f"metric '{n}': format must be currency, percent or number")
        m.setdefault("format", "number")
        if bool(m.get("num")) != bool(m.get("den")):
            fail(f"metric '{n}': a ratio needs both 'num' and 'den'")
    for m in cat.get("metrics", []):
        if m.get("num") and (m["num"] not in names or m["den"] not in names):
            fail(f"metric '{m['name']}': numerator/denominator must be metrics in the catalog")
    dnames = set()
    for d in cat.get("dimensions", []):
        n = d.get("name") or fail("a catalog dimension has no name")
        if n in dnames:
            fail(f"duplicate dimension '{n}' in catalog")
        dnames.add(n)
        d.setdefault("label", n.replace("_", " ").title())
        if d.setdefault("type", "category") not in ("category", "time"):
            fail(f"dimension '{n}': type must be category or time")
    if sum(1 for d in cat["dimensions"] if d["type"] == "time") > 1:
        fail("only one time dimension is supported")
    if not cat.get("metrics"):
        fail("catalog.metrics is empty")


def detect_grain(name: str, sample: list[str]) -> tuple[str, int]:
    s = [str(v) for v in sample[:50]]
    if s and all(re.match(r"^\d{4}-\d{2}-\d{2}", v) for v in s):
        return "day", 365
    if s and all(re.match(r"^\d{4}-\d{2}$", v) for v in s):
        return "month", 12
    if s and all(re.match(r"^\d{4}-?Q[1-4]$", v) for v in s):
        return "quarter", 4
    if s and all(re.match(r"^\d{4}-?W\d{1,2}$", v) for v in s):
        return "week", 52
    if s and all(re.match(r"^(FY)?\d{4}-P\d{1,2}$", v) for v in s):
        mx = max(int(re.search(r"P(\d+)$", v).group(1)) for v in s)
        return "period", 13 if mx > 12 else 12
    n = name.upper()
    for key, grain, ppy in (("WEEK", "week", 52), ("QUARTER", "quarter", 4), ("DAY", "day", 365), ("DATE", "day", 365)):
        if key in n:
            return grain, ppy
    return "month", 12


def values_of(datasets: list[dict[str, Any]], dim: str) -> list[str]:
    out: set[str] = set()
    for ds in datasets:
        if dim in ds["dimensions"]:
            i = ds["columns"].index(dim)
            out.update(r[i] for r in ds["rows"])
    return sorted(out)


def compare_for(metric: str, names: list[str]) -> str | None:
    m = metric.upper()
    if any(w in m for w in PLAN_WORDS):
        return None
    for w in PLAN_WORDS:
        if m.startswith("ACTUAL_") and (w + m[len("ACTUAL"):]) in names:
            return w + m[len("ACTUAL"):]
        for cand in (f"{m}_{w}", f"{w}_{m}"):
            if cand in names:
                return cand
    return None


def answerable(datasets: list[dict[str, Any]], cat_m: dict[str, Any], metrics: list[str], dims: list[str]) -> bool:
    need: set[str] = set()
    for m in metrics:
        d = cat_m[m]
        need.update([d["num"], d["den"]] if d.get("num") else [m])
    for ds in datasets:
        if need <= set(ds["metrics"]) and set(dims) <= set(ds["dimensions"]) and (not ds["partial"] or len(dims) == len(ds["dimensions"])):
            return True
    return False


def tile_metrics(t: dict[str, Any]) -> list[str]:
    ms = [t["metric"]] if t.get("type") == "kpi" and t.get("metric") else list(t.get("metrics", []))
    if t.get("compare"):
        ms.append(t["compare"]["metric"] if isinstance(t["compare"], dict) else t["compare"])
    return ms


def check_tile(spec: dict[str, Any], t: dict[str, Any]) -> dict[str, Any]:
    cat_m = {m["name"]: m for m in spec["catalog"]["metrics"]}
    cat_d = {d["name"] for d in spec["catalog"]["dimensions"]}
    if t.get("type") not in TILE_TYPES:
        fail(f"tile type must be one of {sorted(TILE_TYPES)} (got {t.get('type')!r})")
    t = dict(t)
    ms = tile_metrics(t)
    if not ms:
        fail(f"tile '{t.get('title', '?')}' needs 'metric' (kpi) or 'metrics' (chart or table)")
    for m in ms:
        if m not in cat_m:
            fail(f"tile '{t.get('title', '?')}': unknown metric '{m}'. Known: {sorted(cat_m)}")
    for k in ("x", "groupBy"):
        if t.get(k) and t[k] not in cat_d:
            fail(f"tile '{t.get('title', '?')}': unknown dimension '{t[k]}'. Known: {sorted(cat_d)}")
    if t["type"] in ("bar", "hbar", "line") and not t.get("x"):
        fail(f"tile '{t.get('title', '?')}': {t['type']} needs 'x' (a dimension)")
    if t["type"] == "table" and not t.get("groupBy"):
        fail(f"tile '{t.get('title', '?')}': table needs 'groupBy' (a dimension)")
    if t.get("pop", "none") not in POPS:
        fail(f"tile '{t.get('title', '?')}': pop must be one of {sorted(POPS)}")
    t["span"] = max(2, min(12, int(t.get("span") or 4)))
    t["title"] = str(t.get("title") or "Untitled")[:120]
    return t


def check_filter(spec: dict[str, Any], f: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(f, dict) or not f.get("dimension"):
        fail("a filter needs a 'dimension'")
    op, vals = f.get("op", "in"), f.get("values", [])
    if op not in FILTER_OPS:
        fail(f"filter on {f['dimension']}: unknown op '{op}' (use one of {sorted(FILTER_OPS)})")
    if not isinstance(vals, list) or len(vals) > 500:
        fail(f"filter on {f['dimension']}: values must be a list of at most 500 items")
    if op == "between" and len(vals) != 2:
        fail(f"filter on {f['dimension']}: between needs exactly two values (null for an open end)")
    if op in SINGLE_OPS and len(vals) > 1:
        fail(f"filter on {f['dimension']}: op '{op}' takes one value")
    if f["dimension"] not in {d["name"] for d in spec["catalog"]["dimensions"]}:
        fail(f"filter on unknown dimension '{f['dimension']}'")
    return {"dimension": f["dimension"], "op": op, "values": vals}


def auto_tiles(spec: dict[str, Any], datasets: list[dict[str, Any]]) -> None:
    """Default tiles and filters, same rules as the live server."""
    cat = spec["catalog"]
    names = [m["name"] for m in cat["metrics"]]
    hint = spec.get("auto") or {}
    time_dim = (spec.get("time") or {}).get("dimension")
    metrics = [m for m in hint.get("metrics", []) if m in names] or \
        [n for n in names if not any(w in n.upper() for w in PLAN_WORDS)
         and answerable(datasets, {m["name"]: m for m in cat["metrics"]}, [n], [time_dim] if time_dim else [])][:4]
    if not metrics:
        fail("could not pick default metrics: no dataset has a plain metric by the time dimension. "
             "Add a dataset by time, or list tiles explicitly.")
    cat_m = {m["name"]: m for m in cat["metrics"]}
    pop = hint.get("pop") or (POP_BY_GRAIN.get(spec["time"]["grain"], "none") if time_dim else "none")
    tiles: list[dict[str, Any]] = []

    def add(t: dict[str, Any]) -> None:
        t["id"] = f"t{len(tiles) + 1}"
        tiles.append(t)

    for m in metrics[: int(hint.get("kpis", 4))]:
        k = {"type": "kpi", "title": cat_m[m]["label"], "metric": m, "span": 3, "sparkline": bool(time_dim),
             "pop": pop, "value_mode": "latest" if time_dim else "total"}
        c = compare_for(m, names)
        if c and answerable(datasets, cat_m, [m, c], [time_dim] if time_dim else []):
            k["compare"] = {"metric": c, "label": "vs " + c.split("_")[0].lower() if c.split("_")[0] in PLAN_WORDS else "vs plan"}
        add(k)
    if time_dim:
        c = compare_for(metrics[0], names)
        line = {"type": "line", "title": f"{cat_m[metrics[0]]['label']} over time", "metrics": [metrics[0]], "x": time_dim, "span": 8}
        if c and answerable(datasets, cat_m, [metrics[0], c], [time_dim]):
            line["compare"] = c
        add(line)
    cats = [d for d in cat["dimensions"] if d["type"] != "time"]
    card = {d["name"]: len(values_of(datasets, d["name"])) for d in cats}
    for d in cats:
        d["cardinality"] = card[d["name"]]
    usable = [d for d in cats if answerable(datasets, cat_m, metrics[:1], [d["name"]])]
    short = [d for d in usable if 0 < card[d["name"]] <= 15]
    longd = [d for d in usable if card[d["name"]] > 15]
    if short:
        d = short[0]
        add({"type": "hbar", "title": f"By {d['label']}", "metrics": [m for m in metrics[:3] if answerable(datasets, cat_m, [m], [d['name']])] or metrics[:1],
             "x": d["name"], "limit": 15, "span": 4 if time_dim else 6})
    tbl = (longd or short[1:] or short)[:1]
    if tbl:
        d = tbl[0]
        add({"type": "table", "title": f"{d['label']} detail", "metrics": [m for m in metrics[:4] if answerable(datasets, cat_m, [m], [d['name']])] or metrics[:1],
             "groupBy": d["name"], "limit": 25, "span": 12})
    spec["tiles"] = tiles
    spec["next_tile"] = len(tiles) + 1
    filters = []
    if time_dim:
        filters.append({"dimension": time_dim, "op": "between", "values": [None, None]})
    for d in cats[:2]:
        filters.append({"dimension": d["name"], "op": "in", "values": []})
    spec.setdefault("filters", filters)


# --------------------------------------------------------------------------- edits
def apply_ops(spec: dict[str, Any], ops: list[dict[str, Any]]) -> None:
    for i, op in enumerate(ops):
        kind = op.get("op")

        def need(k: str) -> Any:
            if k not in op:
                fail(f"operation {i} ({kind}) is missing '{k}'")
            return op[k]
        if kind == "set_title":
            spec["title"] = str(need("title"))[:120]
        elif kind == "add_tile":
            t = check_tile(spec, need("tile"))
            t["id"] = f"t{spec['next_tile']}"
            spec["next_tile"] += 1
            idx = op.get("index")
            spec["tiles"].insert(len(spec["tiles"]) if idx is None else int(idx), t)
        elif kind == "update_tile":
            cur = next((t for t in spec["tiles"] if t["id"] == need("id")), None)
            if not cur:
                fail(f"no tile '{op['id']}'. Tiles: {[t['id'] for t in spec['tiles']]}")
            ch = need("changes")
            merged = {**cur, **ch}
            merged = {k: v for k, v in merged.items() if v is not None}
            if ch.get("type") == "kpi" and "metrics" in cur and "metric" not in merged:
                merged["metric"] = cur["metrics"][0]
            if merged["type"] != "kpi" and "metric" in merged and "metrics" not in ch:
                merged["metrics"] = [merged.pop("metric")]
            spec["tiles"][spec["tiles"].index(cur)] = check_tile(spec, merged)
        elif kind == "remove_tile":
            n = len(spec["tiles"])
            spec["tiles"] = [t for t in spec["tiles"] if t["id"] != need("id")]
            if len(spec["tiles"]) == n:
                fail(f"no tile '{op['id']}'")
        elif kind == "move_tile":
            t = next((t for t in spec["tiles"] if t["id"] == need("id")), None)
            if not t:
                fail(f"no tile '{op['id']}'")
            spec["tiles"].remove(t)
            spec["tiles"].insert(max(0, min(len(spec["tiles"]), int(need("index")))), t)
        elif kind == "set_filter":
            nf = check_filter(spec, need("filter"))
            for j, f in enumerate(spec["filters"]):
                if f["dimension"] == nf["dimension"]:
                    spec["filters"][j] = nf
                    break
            else:
                spec["filters"].append(nf)
        elif kind == "remove_filter":
            spec["filters"] = [f for f in spec["filters"] if f["dimension"] != need("dimension")]
        else:
            fail(f"unknown operation '{kind}'. Use set_title, add_tile, update_tile, remove_tile, move_tile, set_filter, remove_filter.")


# --------------------------------------------------------------------------- integrity
def trim_future(spec: dict[str, Any], datasets: list[dict[str, Any]]) -> str | None:
    """Drop periods after the last one with actuals so plan-only future periods do not skew comparisons."""
    metric = spec.get("trim_after_last_actual")
    td = (spec.get("time") or {}).get("dimension")
    if not metric or not td:
        return None
    sums: dict[str, float] = {}
    for ds in datasets:
        if td in ds["dimensions"] and metric in ds["metrics"]:
            ti, mi = ds["columns"].index(td), ds["columns"].index(metric)
            for r in ds["rows"]:
                sums[r[ti]] = sums.get(r[ti], 0.0) + (r[mi] or 0.0)
    live = [p for p, v in sums.items() if v]
    if not live:
        fail(f"trim_after_last_actual: '{metric}' is zero in every period")
    last = max(live)
    spec["_last_kept_period"] = last
    dropped = 0
    for ds in datasets:
        if td in ds["dimensions"]:
            ti = ds["columns"].index(td)
            keep = [r for r in ds["rows"] if r[ti] <= last]
            dropped += len(ds["rows"]) - len(keep)
            ds["rows"] = keep
    return f"kept periods up to {last}; dropped {dropped} later rows" if dropped else f"no periods after {last}"


def reconcile(spec: dict[str, Any], datasets: list[dict[str, Any]], base: Path) -> list[str]:
    """Compare what was copied with independent queries.

    Two forms:
      {"dataset", "metric", "total"[, "where"]}                     one number
      {"dataset", "by": DIM, "file": "totals.json"[, "metrics"]}    one number per group (a query grouped by DIM)

    The tolerance is only the rounding of the copied values: half a unit (``rounded_to``, default 1) per row
    that goes into a sum. It is deliberately not relative to the total: a transposed digit must fail."""
    by_id = {d["id"]: d for d in datasets}
    td = (spec.get("time") or {}).get("dimension")
    last_kept = spec.get("_last_kept_period")
    lines = []
    for n, rc in enumerate(spec.get("reconcile") or [], 1):
        ds = by_id.get(rc.get("dataset")) or fail(f"reconcile[{n}]: unknown dataset '{rc.get('dataset')}'")
        unit = float(rc.get("rounded_to", 1))
        if rc.get("by"):
            dim = rc["by"]
            if dim not in ds["dimensions"]:
                fail(f"reconcile[{n}]: 'by' {dim} is not a dimension of dataset '{ds['id']}'")
            cols, data = read_chunk(base / (rc.get("file") or fail(f"reconcile[{n}]: 'by' needs a 'file' with the grouped query result")))
            low = {c.upper(): i for i, c in enumerate(cols)}
            if dim.upper() not in low:
                fail(f"reconcile[{n}]: file has no column {dim} (found {cols})")
            ms = rc.get("metrics") or [m for m in ds["metrics"] if m.upper() in low]
            if not ms:
                fail(f"reconcile[{n}]: the file shares no metric column with dataset '{ds['id']}'")
            di = ds["columns"].index(dim)
            groups: dict[str, list[list[Any]]] = {}
            for r in ds["rows"]:
                groups.setdefault(r[di], []).append(r)
            expected = {to_dim(r[low[dim.upper()]]): r for r in data}
            for g in groups:                                           # names first: a misspelled group is the clearest error
                if g not in expected:
                    fail(f"reconcile[{n}]: {dim} = {g!r} is in the dataset but not in the independent query. A group was invented or misspelled.")
            for m in ms:
                if m not in ds["metrics"] or m.upper() not in low:
                    fail(f"reconcile[{n}]: metric '{m}' must be in both the dataset and the file")
                mi, fi = ds["columns"].index(m), low[m.upper()]
                for g, rows in groups.items():
                    got, want = sum((r[mi] or 0.0) for r in rows), to_number(expected[g][fi], f"reconcile[{n}] file") or 0.0
                    if abs(got - want) > 0.5 * len(rows) * unit + 0.01:
                        fail(f"reconcile[{n}]: {m} for {dim} = {g!r} sums to {got:,.2f} in the dataset but the independent query says {want:,.2f} "
                             f"(difference {got - want:,.2f}). A value in that group was dropped, mistyped or belongs to another group. "
                             f"Recopy that group's rows exactly and rebuild.")
                for g, r in expected.items():
                    want = to_number(r[fi], "reconcile file") or 0.0
                    if g not in groups and want and not (dim == td and last_kept and g > last_kept):
                        fail(f"reconcile[{n}]: {dim} = {g!r} has {m} = {want:,.2f} in the independent query but no rows in the dataset. Rows were dropped.")
            lines.append(f"reconciled {', '.join(ms)} for each of {len(groups)} {dim} values")
            continue
        m = rc.get("metric")
        if m not in ds["metrics"]:
            fail(f"reconcile[{n}]: dataset '{ds['id']}' has no metric '{m}'")
        where = rc.get("where") or {}
        for k in where:
            if k not in ds["dimensions"]:
                fail(f"reconcile[{n}]: 'where' uses {k}, which is not a dimension of dataset '{ds['id']}'")
        mi = ds["columns"].index(m)
        sel = [r for r in ds["rows"] if all(str(r[ds["columns"].index(k)]) == str(v) for k, v in where.items())]
        got, want = sum((r[mi] or 0.0) for r in sel), float(rc["total"])
        if abs(got - want) > 0.5 * len(sel) * unit + 0.01:
            fail(f"reconcile[{n}]: {m} sums to {got:,.2f} in the dataset but the independent query says {want:,.2f} "
                 f"(difference {got - want:,.2f}). Rows were probably dropped, duplicated or mistyped when the results were copied. "
                 f"Re-copy the query results into the data files and rebuild. If you rounded the values, set \"rounded_to\" (for example 1000) on this reconcile entry.")
        lines.append(f"reconciled {m}{' ' + str(where) if where else ''}: {got:,.2f} vs {want:,.2f}")
    return lines


# --------------------------------------------------------------------------- preview
def fmt_value(v: float | None, m: dict[str, Any]) -> str:
    if v is None:
        return "n/a"
    if m.get("format") == "percent":
        return f"{v * 100:.1f}%"
    if m.get("format") == "currency":
        return f"{'-' if v < 0 else ''}${abs(v):,.0f}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def preview(spec: dict[str, Any], datasets: list[dict[str, Any]]) -> list[str]:
    """What the KPI tiles will show first, so the author can compare with numbers already quoted."""
    td = (spec.get("time") or {}).get("dimension")
    cat_m = {m["name"]: m for m in spec["catalog"]["metrics"]}
    out = []

    def agg(metric: str, ds: dict[str, Any], by_time: bool) -> dict[str, float | None]:
        d = cat_m[metric]
        need = [d["num"], d["den"]] if d.get("num") else [metric]
        idx = [ds["columns"].index(n) for n in need]
        ti = ds["columns"].index(td) if by_time else None
        sums: dict[str, list[float]] = {}
        for r in ds["rows"]:
            k = r[ti] if by_time else "all"
            s = sums.setdefault(k, [0.0] * len(need))
            for j, i in enumerate(idx):
                s[j] += r[i] or 0.0
        return {k: ((v[0] / v[1]) if v[1] else None) if d.get("num") else v[0] for k, v in sums.items()}
    for t in spec["tiles"]:
        if t["type"] != "kpi":
            continue
        m = t["metric"]
        if td and t.get("value_mode") == "latest":
            ds = next((d for d in datasets if td in d["dimensions"] and
                       set([cat_m[m]["num"], cat_m[m]["den"]] if cat_m[m].get("num") else [m]) <= set(d["metrics"]) and not d["partial"]), None)
            if not ds:
                continue
            ser = agg(m, ds, True)
            ps = sorted(ser)
            cur = next((p for p in reversed(ps) if ser[p]), None)
            if cur is None:
                continue
            line = f"  KPI {t['title']}: {fmt_value(ser[cur], cat_m[m])} in {cur}"
            lag = {"MoM": 1, "QoQ": 1 if spec["time"]["grain"] == "quarter" else 3, "WoW": 1 if spec["time"]["grain"] == "week" else 7,
                   "DoD": 1, "YoY": spec["time"].get("periods_per_year", 12)}.get(t.get("pop", "none"))
            if lag and ps.index(cur) - lag >= 0 and ser[ps[ps.index(cur) - lag]]:
                prev = ser[ps[ps.index(cur) - lag]]
                line += f", {t['pop']} {(ser[cur] - prev) / abs(prev):+.1%} (vs {ps[ps.index(cur) - lag]})"
            out.append(line)
        else:
            ds = next((d for d in datasets if set([cat_m[m]["num"], cat_m[m]["den"]] if cat_m[m].get("num") else [m]) <= set(d["metrics"]) and not d["partial"]), None)
            if ds:
                v = agg(m, ds, False)["all"]
                out.append(f"  KPI {t['title']}: {fmt_value(v, cat_m[m])} (total over all rows)")
    return out


# --------------------------------------------------------------------------- definitions
def fill_definitions(spec: dict[str, Any]) -> None:
    d = spec.setdefault("definitions", {})
    d.setdefault("metrics", {})
    d.setdefault("dimensions", {})
    for m in spec["catalog"]["metrics"]:
        e = d["metrics"].setdefault(m["name"], {})
        e.setdefault("label", m["label"])
        if m.get("description") and not e.get("description"):
            e["description"] = m["description"]
        if m.get("num"):
            e.setdefault("formula", f"{m['num']} ÷ {m['den']}")
            e.setdefault("additive", False)
    for dm in spec["catalog"]["dimensions"]:
        e = d["dimensions"].setdefault(dm["name"], {})
        e.setdefault("label", dm["label"])
        if dm.get("description") and not e.get("description"):
            e["description"] = dm["description"]


# --------------------------------------------------------------------------- build
def build(spec_path: Path, out_path: Path | None, ops_path: Path | None, save_spec: bool = True) -> list[str]:
    log: list[str] = []
    spec = load_json(spec_path)
    if not isinstance(spec, dict):
        fail("the spec must be a JSON object")
    base = spec_path.parent
    check_catalog(spec)
    datasets = resolve_datasets(spec, base)
    log.append("datasets: " + ", ".join(f"{d['id']} ({len(d['rows']):,} rows by {d['dimensions'] or 'total'})" for d in datasets))

    spec.setdefault("time", None)
    td = next((d["name"] for d in spec["catalog"]["dimensions"] if d["type"] == "time"), None)
    if td:
        t = spec.get("time") or {}
        t["dimension"] = t.get("dimension") or td
        if t["dimension"] != td:
            fail(f"time.dimension '{t['dimension']}' is not the catalog's time dimension '{td}'")
        if not t.get("grain"):
            t["grain"], t["periods_per_year"] = detect_grain(td, values_of(datasets, td))
        t.setdefault("periods_per_year", {"day": 365, "week": 52, "month": 12, "quarter": 4, "period": 12}.get(t["grain"], 12))
        spec["time"] = t
    else:
        spec["time"] = None

    msg = trim_future(spec, datasets)
    if msg:
        log.append("trim_after_last_actual: " + msg)

    if not spec.get("tiles"):
        auto_tiles(spec, datasets)
        log.append(f"tiles: generated {len(spec['tiles'])} defaults")
    else:
        spec["tiles"] = [check_tile(spec, t) for t in spec["tiles"]]
        for i, t in enumerate(spec["tiles"], 1):
            t.setdefault("id", f"t{i}")
        if len({t["id"] for t in spec["tiles"]}) != len(spec["tiles"]):
            fail("tile ids must be unique")
        spec.setdefault("next_tile", 1 + max(int(re.sub(r"\D", "", t["id"]) or 0) for t in spec["tiles"]))
        spec["filters"] = [check_filter(spec, f) for f in spec.get("filters", [])]
        cats = [d for d in spec["catalog"]["dimensions"]]
        for d in cats:
            if d["type"] != "time":
                d["cardinality"] = len(values_of(datasets, d["name"]))
    if ops_path:
        ops = load_json(ops_path)
        if not isinstance(ops, list):
            fail("the ops file must be a JSON list of operations")
        apply_ops(spec, ops)
        log.append(f"applied {len(ops)} edit operation(s)")
        if save_spec:                                             # keep edits in the spec so the next build starts from them
            spec_file = copy.deepcopy(load_json(spec_path))
            spec_file["tiles"], spec_file["filters"], spec_file["next_tile"], spec_file["title"] = spec["tiles"], spec["filters"], spec["next_tile"], spec["title"]
            spec_path.write_text(json.dumps(spec_file, indent=1, ensure_ascii=False), encoding="utf-8")

    cat_m = {m["name"]: m for m in spec["catalog"]["metrics"]}
    time_dim = spec["time"]["dimension"] if spec["time"] else None
    for t in spec["tiles"]:
        ms = tile_metrics(t)
        dims = [t[k] for k in ("x", "groupBy") if t.get(k)]
        title = t["title"]
        if t["type"] == "kpi":
            total_mode = not time_dim or t.get("value_mode", "latest") == "total"
            wants_series = bool(time_dim) and (not total_mode or t.get("sparkline") or t.get("pop", "none") != "none")
            if total_mode and not answerable(datasets, cat_m, ms, []):
                fail(f"tile '{title}' shows a total of {ms} but no complete dataset has them without a breakdown. "
                     f"Add a dataset with no dimensions (one row), or one by the time dimension.")
            if wants_series and not answerable(datasets, cat_m, ms, [time_dim]):
                fail(f"tile '{title}' needs {ms} by {time_dim} for its sparkline or change, but no dataset provides that. "
                     f"Add a dataset by {time_dim}, or set sparkline false and pop 'none'.")
            if not total_mode and not answerable(datasets, cat_m, ms, [time_dim]):
                fail(f"tile '{title}' needs {ms} by {time_dim} but no dataset provides that.")
        elif not answerable(datasets, cat_m, ms, dims):
            fail(f"tile '{title}' needs {ms} by {dims} but no dataset provides that. Add a dataset with those columns, or change the tile.")

    log += reconcile(spec, datasets, base)
    fill_definitions(spec)
    for k in ("auto", "reconcile", "datasets", "trim_after_last_actual", "_last_kept_period"):
        spec.pop(k, None)

    built_at = spec.pop("built_at", None) or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exported_by = spec.pop("exported_by", None)
    payload_core = {"spec": spec, "datasets": datasets}
    build_id = hashlib.sha256(json.dumps(payload_core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    spec["id"] = "snap_" + build_id
    spec["version"] = 1
    spec.setdefault("snapshot", True)
    payload = {**payload_core, "built_at": built_at, "exported_by": exported_by, "build_id": build_id}

    log.append("preview of what the dashboard opens with:")
    log += preview(spec, datasets) or ["  (no KPI tiles)"]

    if out_path:
        if not TEMPLATE.exists():
            fail(f"template missing: {TEMPLATE}")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        text = text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")   # no "<" can reach the HTML parser
        html = TEMPLATE.read_text(encoding="utf-8").replace("__SNAPSHOT_JSON__", text, 1)
        html = html.replace("<title>Semantic dashboard</title>", "<title>" + _esc(spec["title"]) + "</title>", 1)
        if len(html.encode()) > MAX_BYTES:
            fail(f"the output would be {len(html) / 1e6:.1f} MB, over the {MAX_BYTES // 2**20} MB limit. Use fewer rows.")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        log.append(f"wrote {out_path} ({len(html) / 1024:,.0f} KB, {sum(len(d['rows']) for d in datasets):,} rows)")
    return log


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--out", type=Path, help="output HTML (omit to validate only)")
    ap.add_argument("--ops", type=Path, help="JSON list of edit operations to apply first")
    a = ap.parse_args()
    try:
        for line in build(a.spec, a.out, a.ops):
            print(line)
    except SpecError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
