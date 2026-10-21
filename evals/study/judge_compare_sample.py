#!/usr/bin/env python3
"""Choose the cross-vendor judge: each Gemini candidate against Astra (and Sol) on 100 pilot outputs.

Subcommands
  sample    draw the sample and write $CMP/sample.json (ids and output hashes only, no text)
  report    agreement of each candidate with Astra and Sol on the sample; prints a report and
            writes $CMP/agreement.json (numbers only)
  selftest  unit tests for the Gemini call, the key lookup, the sampler and the report against a
            local fake HTTP server (no key, no network); when the pilot data is present, also an
            end-to-end run of judge_pilot.py on the sample against the fake server
$CMP is $POLISH_EVAL_DATA/Processed/polish-open-source-prose/gemini-compare.

Sample. The pool is the 1,368 judged pilot outputs (19 cases; the cases in the pilot's
judge-excluded.json left out). Strata are evidence level x editing model: 12 strata of 114
outputs, each stratum 19 cases x 3 instructions x 2 runs. With n = 100, each stratum gets 8 or
9 outputs (which four get 9 is drawn) and each case 5 or 6 (which five get 6 is drawn); a case x
stratum cell holds at most one sampled output. The cells form a random 0/1 table with those
margins: a greedy fill (each case, in random order, takes the strata with the most quota left,
ties at random), then 20,000 random checkerboard swaps, which keep both margins. In each chosen
cell, visited in random order, the instruction is the least used so far (ties at random), so
instructions come out 34/33/33, and the run is drawn at random. All draws come from
random.Random("gemini-compare/<seed>"), seed 20261021 by default, and do not depend on Python's
hash seed or the order of the records file.

Judging is judge_pilot.py with --sample and --out, once per candidate (per-case batches of 20,
of 5 for the large-diff case, the same prompt and labels as the pilot judges):
  judge_pilot.py --judges gemini-pro --sample $CMP/sample.json --out $CMP/judgments.json
Astra and Sol are read from pilot-judgments.json, where they judged the same outputs in
batches of 20 within the whole case. If Astra (or Sol) is also run on the sample into
$CMP/judgments.json, the report adds it as "astra-rerun": the same judge on the same outputs in
the sample's smaller batches, a ceiling for what another judge can reach.

Report: per pair (each candidate with Astra and with Sol, Astra with Sol for reference, and the
two candidates with each other): raw agreement and Cohen's kappa per label and on complete
clean fix, linear and quadratic weighted kappa for addressed (judge_agreement.py's functions);
which judge gave the higher value; each judge's label rates on the sample; for complete clean
fix, a 95% case-bootstrap interval (2,000 resamples of the 19 cases) for kappa with Astra and
Sol and for the difference between the candidates; each candidate's calls, retries, outcomes,
tokens, seconds, finish reasons and model versions from the usage log.

Usage: POLISH_EVAL_DATA=/mnt/d/Data .venv/bin/python evals/study/judge_compare_sample.py
         sample [--seed N] [--n 100] [--dry-run] [--force]
         report [--judgments PATH] [--usage PATH] [--out PATH]
         selftest [-v]
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.server
import io
import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_agreement as ja  # noqa: E402
import judge_pilot as jp  # noqa: E402
import pilot_common as pc  # noqa: E402

CMP = pc.PROC / "gemini-compare"
SAMPLE = CMP / "sample.json"
JUDGMENTS = CMP / "judgments.json"
USAGE = CMP / "judge-usage.jsonl"
REPORT = CMP / "agreement.json"
SEED, N, SWAPS, BOOT = 20261021, 100, 20_000, 2000
CANDIDATES = list(jp.GEMINI_MODELS)
REFERENCE = ["astra", "sol"]
ITEM_FIELDS = ("case", "label", "model", "evidence", "instruction", "run", "output_sha")
METHOD = ("strata evidence x model (12); stratum quotas 8 or 9 and case quotas 5 or 6, the larger quotas drawn; "
          "at most one output per case x stratum cell; cells by greedy fill then 20,000 checkerboard swaps "
          "(margins kept); per cell the least-used instruction so far (ties at random, cells in random order) "
          "and a random run; random.Random('gemini-compare/<seed>')")


# ---------------------------------------------------------------- sample

def pool(records_path: Path = jp.RECORDS, excluded_path: Path = jp.EXCLUDED) -> tuple[list[dict], list[str], str]:
    raw = records_path.read_bytes()
    excluded = json.loads(excluded_path.read_text())["cases"] if excluded_path.exists() else []
    records = [r for r in json.loads(raw)["records"] if r["case"] not in excluded]
    return records, excluded, hashlib.sha256(raw).hexdigest()


def draw(records: list[dict], n: int = N, seed: int = SEED) -> tuple[list[dict], dict]:
    """The sample (sorted by case and label) and its margins; see the module docstring."""
    rng = random.Random(f"gemini-compare/{seed}")
    strata = [(ev, m) for ev in pc.EVIDENCE_LEVELS for m in pc.MODELS]
    cases = sorted({r["case"] for r in records})
    cells: dict = {}
    for r in records:
        cells.setdefault((r["case"], (r["evidence"], r["model"])), []).append(r)
    if any((c, s) not in cells for c in cases for s in strata) or len(cells) != len(cases) * len(strata):
        raise SystemExit("every case must have outputs in every evidence x model stratum, and no other strata")
    if n > len(cases) * len(strata):
        raise SystemExit(f"n {n} exceeds the {len(cases) * len(strata)} case x stratum cells")

    def quotas(keys: list) -> dict:
        base, extra = divmod(n, len(keys))
        plus = set(rng.sample(keys, extra))
        return {k: base + (k in plus) for k in keys}
    row, col = quotas(cases), quotas(strata)
    if max(row.values()) > len(strata) or max(col.values()) > len(cases):
        raise SystemExit("quota larger than the cells available")
    left, chosen = dict(col), []
    for c in rng.sample(cases, len(cases)):
        ranked = sorted(strata, key=lambda s: (-left[s], rng.random()))
        for s in ranked[:row[c]]:
            chosen.append((c, s))
            left[s] -= 1
    assert not any(left.values()), "greedy fill left stratum quota unfilled"
    on = set(chosen)
    for _ in range(SWAPS):
        i, j = rng.randrange(len(chosen)), rng.randrange(len(chosen))
        (c1, s1), (c2, s2) = chosen[i], chosen[j]
        if c1 == c2 or s1 == s2 or (c1, s2) in on or (c2, s1) in on:
            continue
        on -= {(c1, s1), (c2, s2)}
        on |= {(c1, s2), (c2, s1)}
        chosen[i], chosen[j] = (c1, s2), (c2, s1)
    used: Counter = Counter()
    picked = []
    for c, s in rng.sample(sorted(chosen), len(chosen)):
        rs = sorted(cells[(c, s)], key=lambda r: (r["instruction"], r["run"]))
        instrs = sorted({r["instruction"] for r in rs})
        low = min(used[i] for i in instrs)
        ins = rng.choice([i for i in instrs if used[i] == low])
        used[ins] += 1
        picked.append(rng.choice([r for r in rs if r["instruction"] == ins]))
    items = sorted(({"case": r["case"], "label": jp.label_for(r), "model": r["model"], "evidence": r["evidence"],
                     "instruction": r["instruction"], "run": r["run"], "output_sha": jp.output_hash(r)} for r in picked),
                   key=lambda x: (x["case"], x["label"]))
    info = {"seed": seed, "n": len(items), "method": METHOD, "pool_outputs": len(records), "pool_cases": len(cases),
            "per_stratum": {f"{ev}/{m}": sum(1 for x in items if (x["evidence"], x["model"]) == (ev, m)) for ev, m in strata},
            "per_case": dict(Counter(x["case"] for x in items)),
            "per_evidence": dict(Counter(x["evidence"] for x in items)),
            "per_model": dict(Counter(x["model"] for x in items)),
            "per_instruction": dict(Counter(x["instruction"] for x in items)),
            "per_run": dict(Counter(x["run"] for x in items))}
    return items, info


def cmd_sample(o) -> None:
    records, excluded, sha = pool()
    items, info = draw(records, o.n, o.seed)
    doc = {**info, "records_file": str(jp.RECORDS), "records_sha256": sha, "excluded_cases": excluded,
           "drawn": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "items": items}
    print(f"{info['n']} outputs from {len(info['per_case'])} cases (pool {info['pool_outputs']} from {info['pool_cases']} "
          f"cases, excluded {', '.join(excluded) or 'none'}), seed {o.seed}")
    print(f"per stratum {sorted(Counter(info['per_stratum'].values()).items())} (count: strata); "
          f"per case {sorted(Counter(info['per_case'].values()).items())} (count: cases)")
    print(f"evidence {info['per_evidence']}; model {info['per_model']}; instruction {info['per_instruction']}; "
          f"run {info['per_run']}")
    if o.dry_run:
        return
    if SAMPLE.exists() and not o.force:
        old = json.loads(SAMPLE.read_text())
        if old["items"] == items:
            print(f"{SAMPLE} already holds this sample; unchanged")
            return
        raise SystemExit(f"{SAMPLE} holds a different sample (seed {old.get('seed')}); --force replaces it")
    jp.write_atomic(SAMPLE, json.dumps(doc, indent=1) + "\n")
    print(f"wrote {SAMPLE}")


# ---------------------------------------------------------------- report

def load_rows(sample: dict, pilot: dict, compare: dict) -> tuple[dict, dict]:
    """{judge: {(case, label): row}} for the sampled outputs; Astra and Sol from the pilot file,
    the candidates (and any reference judge rerun on the sample, as "<judge>-rerun") from the
    comparison file. Rows whose output hash differs are counted as stale and left out."""
    rows: dict = {}
    stale: Counter = Counter()
    sources = [(j, j, pilot) for j in REFERENCE] + [(j, j, compare) for j in CANDIDATES] \
        + [(f"{j}-rerun", j, compare) for j in REFERENCE]
    for name, j, src in sources:
        got = {}
        for it in sample["items"]:
            r = src.get(jp.result_key(j, it))
            if r and r[0].get("output_sha") == it["output_sha"]:
                got[(it["case"], it["label"])] = r[0]
            elif r:
                stale[name] += 1
        if got:
            rows[name] = got
    return rows, dict(stale)


def pair_stats(rows: dict, a: str, b: str) -> dict:
    keys = sorted(set(rows[a]) & set(rows[b]))
    if not keys:
        return {"n": 0}
    full = [{a: rows[a][k], b: rows[b][k]} for k in keys]
    agr = ja.agreement(full, [a, b])
    out: dict = {"n": len(keys)}
    for lab in ja.LABELS:
        out[lab] = agr[lab]["pairwise"][f"{a}-{b}"]
    out["direction"] = {lab: {f"{a}_higher": sum(1 for x in full if float(ja.value(x[a], lab)) > float(ja.value(x[b], lab))),
                              f"{b}_higher": sum(1 for x in full if float(ja.value(x[a], lab)) < float(ja.value(x[b], lab)))}
                        for lab in ("addressed", "code_consistent", "invented", "damaged", "complete")}
    out["all_five_labels_equal"] = sum(1 for x in full if all(ja.value(x[a], lab) == ja.value(x[b], lab)
                                                               for lab in ja.LABELS[:5]))
    return out


def kappa_complete(rows: dict, a: str, b: str, keys: list) -> float | None:
    return ja.cohen([ja.value(rows[a][k], "complete") for k in keys], [ja.value(rows[b][k], "complete") for k in keys],
                    ja.CATS["complete"])


def boot(rows: dict, stat, keys: list, seed: int = SEED, b: int = BOOT) -> list | None:
    """95% percentile interval of stat(keys) over case-bootstrap resamples; resamples where the
    statistic is undefined are skipped (their count is not reported; with ~100 outputs it is rare)."""
    by_case: dict = {}
    for k in keys:
        by_case.setdefault(k[0], []).append(k)
    cases = sorted(by_case)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(b):
        ks = [k for i in rng.integers(0, len(cases), len(cases)) for k in by_case[cases[i]]]
        v = stat(ks)
        if v is not None:
            vals.append(v)
    if len(vals) < b // 2:
        return None
    return [ja.r3(float(np.percentile(vals, 2.5))), ja.r3(float(np.percentile(vals, 97.5)))]


def compare(sample: dict, rows: dict) -> dict:
    present = [j for j in [*REFERENCE, *(f"{j}-rerun" for j in REFERENCE), *CANDIDATES] if j in rows]
    cands = [j for j in CANDIDATES if j in rows]
    pairs = [(r, c) for c in cands for r in REFERENCE if r in rows] + [("astra", "sol")] \
        + [(r, f"{r}-rerun") for r in REFERENCE if f"{r}-rerun" in rows] + list(itertools.combinations(cands, 2))
    pairs = [(a, b) for a, b in pairs if a in rows and b in rows]
    s: dict = {"n_sample": len(sample["items"]), "seed": sample.get("seed"), "judged": {j: len(rows[j]) for j in present},
               "judge_models": {j: sorted({r.get("judge_model") or jp.JUDGES[j.removesuffix("-rerun")][0]
                                           for r in rows[j].values()}) for j in present},
               "pairs": {f"{a}-{b}": pair_stats(rows, a, b) for a, b in pairs},
               "rates": {j: ja.rates(list(rows[j].values())) for j in present},
               "complete_kappa_ci": {}, "complete_kappa_difference": {}}
    for a, b in pairs:
        keys = sorted(set(rows[a]) & set(rows[b]))
        if keys:
            s["complete_kappa_ci"][f"{a}-{b}"] = boot(rows, lambda ks, a=a, b=b: kappa_complete(rows, a, b, ks), keys)
    for ref in REFERENCE:
        if ref in rows and len(cands) == 2:
            c1, c2 = cands
            keys = sorted(set(rows[ref]) & set(rows[c1]) & set(rows[c2]))
            if keys:
                def diff(ks, ref=ref, c1=c1, c2=c2):
                    k1, k2 = kappa_complete(rows, ref, c1, ks), kappa_complete(rows, ref, c2, ks)
                    return None if k1 is None or k2 is None else k1 - k2
                s["complete_kappa_difference"][f"{ref}: {c1} - {c2}"] = {
                    "n": len(keys), "difference": ja.r3(diff(keys)), "ci95": boot(rows, diff, keys)}
    return s


def usage_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def cmd_report(o) -> dict:
    sample = json.loads(o.sample.read_text())
    pilot = json.loads(o.pilot_judgments.read_text())
    comp = json.loads(o.judgments.read_text()) if o.judgments.exists() else {}
    rows, stale = load_rows(sample, pilot, comp)
    s = compare(sample, rows)
    s["stale_judgments"] = stale
    usage = usage_rows(o.usage)
    s["usage"] = {}
    for j in CANDIDATES:
        us = [u for u in usage if u.get("judge") == j]
        if us:
            s["usage"][j] = {**ja.usage_summary(usage, j),
                             "http_status": dict(Counter(str(u.get("http_status")) for u in us)),
                             "finish_reason": dict(Counter(str(u.get("finish_reason")) for u in us)),
                             "model_version": sorted({str(u.get("model_version")) for u in us}),
                             "thinking_level": sorted({str(u.get("thinking_level")) for u in us})}
    full = pc.PROC / "pilot-judge-agreement.json"
    if full.exists():
        f = json.loads(full.read_text()).get("agreement", {})
        s["pilot_astra_sol_all_outputs"] = {lab: f.get(lab, {}).get("pairwise", {}).get("astra-sol") for lab in ja.LABELS}
        s["pilot_astra_sol_all_outputs"]["n"] = f.get("n")
    jp.write_atomic(o.out, json.dumps(s, indent=1) + "\n")
    print_report(s)
    print(f"\nwrote {o.out}")
    return s


def print_report(s: dict) -> None:
    print(f"sample: {s['n_sample']} outputs (seed {s['seed']}); judged: "
          + ", ".join(f"{j} {n} ({', '.join(s['judge_models'][j])})" for j, n in s["judged"].items()))
    if s.get("stale_judgments"):
        print(f"stale judgments left out: {s['stale_judgments']}")
    labs = ja.LABELS
    print("\nraw agreement / Cohen's kappa; addressed also linear / quadratic weighted kappa")
    print(f"{'pair':<26}{'n':>4}" + "".join(f"{lab[:15]:>16}" for lab in labs) + f"{'addr lin/quad':>16}")
    for p, d in s["pairs"].items():
        if not d["n"]:
            continue
        print(f"{p:<26}{d['n']:>4}" + "".join(f"{str(d[lab]['raw']) + ' / ' + str(d[lab]['kappa']):>16}" for lab in labs)
              + f"{str(d['addressed']['kappa_linear']) + ' / ' + str(d['addressed']['kappa_quadratic']):>16}")
    if s.get("pilot_astra_sol_all_outputs", {}).get("complete"):
        f = s["pilot_astra_sol_all_outputs"]
        print(f"{'astra-sol, all pilot':<26}{f['n']:>4}"
              + "".join(f"{str(f[lab]['raw']) + ' / ' + str(f[lab]['kappa']):>16}" for lab in labs)
              + f"{str(f['addressed']['kappa_linear']) + ' / ' + str(f['addressed']['kappa_quadratic']):>16}")
    print(f"\ncomplete clean fix kappa, 95% case-bootstrap interval ({BOOT:,} resamples):")
    for p, ci in s["complete_kappa_ci"].items():
        print(f"  {p:<26} {s['pairs'][p]['complete']['kappa']} {ci}")
    for p, d in s["complete_kappa_difference"].items():
        print(f"  difference in kappa with {p}: {d['difference']} {d['ci95']} on {d['n']} outputs")
    print("\nwho gives the higher value (first / second judge of the pair); all five labels equal")
    for p, d in s["pairs"].items():
        if d["n"]:
            print(f"  {p:<26}" + "; ".join(f"{lab} {'/'.join(str(v) for v in dd.values())}" for lab, dd in d["direction"].items())
                  + f"; all five equal {d['all_five_labels_equal']}/{d['n']}")
    print("\nlabel rates on the sample")
    for j, r in s["rates"].items():
        print(f"  {j:<13} addressed mean {r['addressed_mean']} {r['addressed']}; code_consistent {r['code_consistent']}; "
              f"invented {r['invented']}; damaged {r['damaged']}; asked {r['asked']}; complete {r['complete']}")
    for j, u in s["usage"].items():
        t = u["tokens"]
        print(f"\n{j}: {u['attempts']} attempts ({u['calls']}), {u['retries']} retries, outcomes {u['outcomes']}, "
              f"rate-limited {u['rate_limited_attempts']}; tokens input {t['input_tokens']:,} (cached {t['cached_input_tokens']:,}), "
              f"output {t['output_tokens']:,} (thinking {t['reasoning_output_tokens']:,}); {u['seconds']:,.0f}s; "
              f"HTTP {u['http_status']}; finish {u['finish_reason']}; model version {u['model_version']}; "
              f"thinking {u['thinking_level']}")


# ---------------------------------------------------------------- self-test

KEY = "fake-key-Zq81-not-real"


def gen_response(text: str, usage: dict | None = None, finish: str = "STOP", parts: list | None = None) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": parts if parts is not None else [{"text": text}]},
                            "finishReason": finish, "index": 0}],
            "usageMetadata": usage or {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
            "modelVersion": "fake-model-001", "responseId": "r1"}


def plain_row(label: str) -> dict:
    h = int(hashlib.sha1(label.encode()).hexdigest(), 16)
    return {"addressed": [0, 0.5, 1][h % 3], "code_consistent": bool(h & 8), "invented": bool(h & 16),
            "damaged": bool(h & 32), "asked": "none", "note": "fake"}


class FakeGemini:
    """A local stand-in for the Gemini API. Replies come from `script` ((status, body, delay)
    tuples, in order); when it is empty, a generateContent call gets a valid judgment for every
    <output label> in the prompt (values from `answer(model, label)`) and a models call gets the
    two configured ids."""

    def __init__(self, answer=None):
        self.script: list = []
        self.requests: list = []
        self.answer = answer or (lambda model, label: plain_row(label))
        self.lock = threading.Lock()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                with outer.lock:
                    outer.requests.append({"method": self.command, "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                           "body": body})
                    step = outer.script.pop(0) if outer.script else None
                status, payload, delay = step if step else (200, outer.default(self.path, body), 0)
                time.sleep(delay)
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            do_GET = do_POST = reply

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1beta"

    def default(self, path: str, body: bytes) -> dict:
        if "/models?" in path or path.endswith("/models"):
            return {"models": [{"name": f"models/{m}", "displayName": m, "supportedGenerationMethods": ["generateContent"],
                                "inputTokenLimit": 1048576, "outputTokenLimit": 65536, "thinking": True}
                               for m in jp.GEMINI_MODELS.values()]}
        model = path.split("/models/", 1)[1].split(":", 1)[0]
        prompt = json.loads(body)["contents"][0]["parts"][0]["text"]
        labels = re.findall(r'<output label="([0-9a-f]{8})">', prompt)
        rows = [{"label": lab, **self.answer(model, lab)} for lab in labels]
        return gen_response("```json\n" + json.dumps(rows) + "\n```",
                            {"promptTokenCount": len(prompt) // 3, "cachedContentTokenCount": 0,
                             "candidatesTokenCount": 40 * len(rows), "thoughtsTokenCount": 500,
                             "totalTokenCount": len(prompt) // 3 + 40 * len(rows) + 500})

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def fake_items(n: int, case: str = "a2-test-1") -> list[dict]:
    rs = [{"model": "m", "evidence": "E1", "instruction": "none", "run": str(i), "case": case,
           "output": f"revised text {i}", "note": ""} for i in range(n)]
    return [dict(r, label=jp.label_for(r), output_sha=jp.output_hash(r)) for r in rs]


def fake_batch(n: int = 3, large: bool = False) -> dict:
    items = fake_items(n)
    outs = "\n\n".join(jp.render_output(r) for r in items)
    prompt = jp.PROMPT.format(original="o", review="r", ci="c", diff_block=jp.DIFF_INLINE.format(diff="d"), outputs=outs)
    return {"key": jp.batch_id("a2-test-1", [i["label"] for i in items]), "case": "a2-test-1", "items": items,
            "prompt": prompt, "prompt_file_mode": prompt, "large": large, "diff": "d", "diff_as_file": False,
            "diff_truncated": False}


def valid_answer(p: dict) -> str:
    return json.dumps([{"label": it["label"], **plain_row(it["label"])} for it in p["items"]])


class GeminiTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.env = {k: os.environ.get(k) for k in ("GEMINI_API_KEY", "GEMINI_ENV_FILE", "no_proxy", "NO_PROXY")}
        os.environ["GEMINI_API_KEY"] = KEY
        os.environ["GEMINI_ENV_FILE"] = str(self.dir / "no-such.env")  # never the real key file
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        self.fake = FakeGemini()
        self.saved = (jp.GEMINI_API, jp.GEMINI_TIMEOUT)
        jp.GEMINI_API = self.fake.base
        jp.HALTED.clear()
        jp.STOP.clear()
        self.store = jp.Store(self.dir / "judgments.json", self.dir / "usage.jsonl")
        self.sleeps: list = []
        self.out = io.StringIO()

    def tearDown(self):
        self.fake.close()
        jp.GEMINI_API, jp.GEMINI_TIMEOUT = self.saved
        jp.HALTED.clear()
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        written = "".join(p.read_text() for p in self.dir.glob("*") if p.is_file())
        self.assertNotIn(KEY, written + self.out.getvalue(), "the key leaked into a file or the output")
        self.tmp.cleanup()

    def run_judge(self, p: dict, judge: str = "gemini-pro") -> dict:
        with contextlib.redirect_stdout(self.out):
            kept, _ = jp.judge_call(judge, p, self.store, sleep=self.sleeps.append)
        return kept

    def logged(self) -> list[dict]:
        return usage_rows(self.store.usage)


class KeyTests(GeminiTestBase):
    def test_env_wins_over_file(self):
        f = self.dir / "k.env"
        f.write_text("GEMINI_API_KEY=from-file\n")
        os.environ["GEMINI_ENV_FILE"] = str(f)
        self.assertEqual(jp.gemini_key(), KEY)

    def test_file_line_only(self):
        f = self.dir / "k.env"
        f.write_text("# comment\nOTHER_SECRET=zzz\nexport GEMINI_API_KEY=\"abc123\"  \nMORE=1\n")
        os.environ.pop("GEMINI_API_KEY")
        os.environ["GEMINI_ENV_FILE"] = str(f)
        self.assertEqual(jp.gemini_key(), "abc123")

    def test_missing_everywhere(self):
        os.environ.pop("GEMINI_API_KEY")
        with self.assertRaises(jp.NoGeminiKey) as cm:
            jp.gemini_key()
        self.assertIn("GEMINI_API_KEY is not set", str(cm.exception))

    def test_file_without_the_line_does_not_echo_content(self):
        f = self.dir / "k.env"
        f.write_text("GEMINI_KEY=secret-looking-value\n")
        os.environ.pop("GEMINI_API_KEY")
        os.environ["GEMINI_ENV_FILE"] = str(f)
        with self.assertRaises(jp.NoGeminiKey) as cm:
            jp.gemini_key()
        self.assertNotIn("secret-looking-value", str(cm.exception))
        f.unlink()

    def test_call_without_key_is_fatal_and_sends_nothing(self):
        os.environ.pop("GEMINI_API_KEY")
        kept = self.run_judge(fake_batch())
        self.assertEqual(kept, {})
        self.assertEqual(self.fake.requests, [])
        rows = self.logged()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["fatal"])
        self.assertIn("gemini-pro", jp.HALTED)
        self.assertEqual(self.sleeps, [])


class CallTests(GeminiTestBase):
    def test_success_request_shape_and_usage_mapping(self):
        p = fake_batch(3)
        um = {"promptTokenCount": 1200, "cachedContentTokenCount": 200, "candidatesTokenCount": 90,
              "thoughtsTokenCount": 700, "totalTokenCount": 1990}
        self.fake.script.append((200, gen_response("", um, parts=[{"text": "thinking about it", "thought": True},
                                                                  {"text": valid_answer(p)}]), 0))
        text, usage = jp.call_gemini("gemini-flash", p)
        self.assertEqual(json.loads(text)[0]["label"], p["items"][0]["label"])
        self.assertNotIn("thinking about it", text)
        self.assertEqual((usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"],
                          usage["reasoning_output_tokens"], usage["turns"]), (1200, 200, 790, 700, 1))
        self.assertEqual(usage["gemini_usage"], um)
        self.assertEqual((usage["http_status"], usage["finish_reason"], usage["model_version"], usage["error"]),
                         (200, "STOP", "fake-model-001", None))
        self.assertEqual((usage["model"], usage["effort"], usage["thinking_level"]), (jp.GEMINI_MODELS["gemini-flash"], "high", "high"))
        req = self.fake.requests[0]
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["path"], f"/v1beta/models/{jp.GEMINI_MODELS['gemini-flash']}:generateContent")
        self.assertEqual(req["headers"].get("x-goog-api-key"), KEY)
        self.assertNotIn(KEY, req["path"])
        body = json.loads(req["body"])
        self.assertEqual(body, {"contents": [{"role": "user", "parts": [{"text": p["prompt"]}]}],
                                "generationConfig": {"thinkingConfig": {"thinkingLevel": "high"}}})
        self.assertNotIn(KEY, json.dumps(usage))

    def test_429_then_success(self):
        p = fake_batch(3)
        self.fake.script += [(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}}, 0),
                             (200, gen_response(valid_answer(p)), 0)]
        kept = self.run_judge(p)
        self.assertEqual(set(kept), {it["label"] for it in p["items"]})
        self.assertEqual([r["outcome"] for r in self.logged()], ["rate_limited", "complete"])
        self.assertTrue(self.logged()[0]["rate_limited"])
        self.assertEqual(len(self.sleeps), 1)
        self.assertTrue(30 <= self.sleeps[0] <= 90, self.sleeps)  # 60 s first wait, jitter 0.5-1.5

    def test_500_and_503_are_failures_with_backoff(self):
        p = fake_batch(2)
        self.fake.script += [(500, {"error": {"code": 500, "status": "INTERNAL", "message": "internal"}}, 0),
                             (503, b"<html>overloaded</html>", 0), (200, gen_response(valid_answer(p)), 0)]
        kept = self.run_judge(p)
        self.assertEqual(len(kept), 2)
        rows = self.logged()
        self.assertEqual([r["outcome"] for r in rows], ["failed", "failed", "complete"])
        self.assertEqual([r["http_status"] for r in rows], [500, 503, 200])
        self.assertFalse(any(r["rate_limited"] or r["fatal"] for r in rows))
        self.assertIn("HTTP 503", rows[1]["error"])
        self.assertTrue(15 <= self.sleeps[0] <= 45 and 30 <= self.sleeps[1] <= 90, self.sleeps)

    def test_malformed_json_is_a_failure_not_an_exception(self):
        p = fake_batch(2)
        self.fake.script += [(200, b"{not json", 0), (200, b"[1, 2]", 0), (200, gen_response(valid_answer(p)), 0)]
        text, usage = jp.call_gemini("gemini-pro", p)
        self.assertEqual(text, "")
        self.assertIn("malformed JSON", usage["error"])
        kept = self.run_judge(p)
        self.assertEqual(len(kept), 2)
        self.assertEqual([r["outcome"] for r in self.logged()], ["failed", "complete"])

    def test_fatal_4xx_is_not_retried_and_key_is_scrubbed(self):
        p = fake_batch(2)
        self.fake.script.append((400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                                 "message": f"API key not valid: {KEY}"}}, 0))
        kept = self.run_judge(p)
        self.assertEqual(kept, {})
        rows = self.logged()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["fatal"])
        self.assertIn("[key]", rows[0]["error"])
        self.assertEqual(self.sleeps, [])
        self.assertIn("gemini-pro", jp.HALTED)
        self.assertEqual(self.run_judge(fake_batch(1)), {})  # a halted judge makes no further calls
        self.assertEqual(len(self.fake.requests), 1)

    def test_timeout(self):
        jp.GEMINI_TIMEOUT = 0.5
        p = fake_batch(1)
        self.fake.script.append((200, gen_response(valid_answer(p)), 2.0))
        text, usage = jp.call_gemini("gemini-pro", p)
        self.assertEqual(text, "")
        self.assertTrue(usage["error"].startswith("timeout"), usage["error"])

    def test_connection_refused(self):
        jp.GEMINI_API = "http://127.0.0.1:9/v1beta"
        text, usage = jp.call_gemini("gemini-pro", fake_batch(1))
        self.assertEqual(text, "")
        self.assertTrue(usage["error"])
        self.assertFalse(usage["fatal"])

    def test_blocked_prompt_and_max_tokens(self):
        p = fake_batch(1)
        self.fake.script += [(200, {"promptFeedback": {"blockReason": "SAFETY"}, "usageMetadata": {"promptTokenCount": 9}}, 0),
                             (200, gen_response("", finish="MAX_TOKENS", parts=[]), 0)]
        text, usage = jp.call_gemini("gemini-pro", p)
        self.assertEqual((text, usage["input_tokens"]), ("", 9))
        self.assertIn("SAFETY", usage["error"])
        text, usage = jp.call_gemini("gemini-pro", p)
        self.assertIn("MAX_TOKENS", usage["error"])

    def test_no_file_route_for_gemini(self):
        p = fake_batch(2, large=True)
        self.fake.script += [(200, gen_response("I cannot produce JSON."), 0), (200, gen_response(valid_answer(p)), 0)]
        kept = self.run_judge(p)
        self.assertEqual(len(kept), 2)
        self.assertEqual([r["diff_as_file"] for r in self.logged()], [False, False])
        self.assertEqual([r["outcome"] for r in self.logged()], ["unparsable", "complete"])
        self.assertEqual({json.loads(r["body"])["contents"][0]["parts"][0]["text"] for r in self.fake.requests}, {p["prompt"]})

    def test_partial_batch_then_single(self):
        p = fake_batch(3)
        rows = json.loads(valid_answer(p))[:2]
        self.fake.script.append((200, gen_response(json.dumps(rows)), 0))  # the single call gets the default reply
        opts = argparse.Namespace(file_threshold=None, truncate_over=250_000)
        ctx = {"case": "a2-test-1", "diff": "d", "large": False, "static": dict(original="o", review="r", ci="c")}
        with contextlib.redirect_stdout(self.out):
            left = jp.judge_batch("gemini-pro", p, ctx, self.store, opts, sleep=self.sleeps.append)
        self.assertEqual(left, [])
        saved = self.store.read()
        self.assertEqual(len(saved), 3)
        self.assertTrue(all(v[0]["judge_model"] == jp.GEMINI_MODELS["gemini-pro"] for v in saved.values()))
        self.assertEqual([r["kind"] for r in self.logged()], ["batch", "single"])

    def test_list_models_pages_and_check(self):
        page1 = {"models": [{"name": f"models/{jp.GEMINI_MODELS['gemini-pro']}", "supportedGenerationMethods": ["generateContent"]}],
                 "nextPageToken": "t2"}
        page2 = {"models": [{"name": f"models/{jp.GEMINI_MODELS['gemini-flash']}", "supportedGenerationMethods": ["generateContent"]}]}
        self.fake.script += [(200, page1, 0), (200, page2, 0)]
        with contextlib.redirect_stdout(self.out):
            self.assertEqual(jp.list_gemini_models(), 0)
        self.assertIn("pageToken=t2", self.fake.requests[1]["path"])
        self.assertEqual(self.out.getvalue().count(" found"), 2)
        self.fake.script.append((200, {"models": [{"name": "models/gemini-other"}]}, 0))
        with contextlib.redirect_stdout(self.out):
            self.assertEqual(jp.list_gemini_models(), 1)


def synthetic_records() -> list[dict]:
    return [{"case": f"a2-x-{c:02d}", "evidence": ev, "model": m, "instruction": ins, "run": run,
             "output": f"{c}{ev}{m}{ins}{run}", "note": ""}
            for c in range(19) for ev in pc.EVIDENCE_LEVELS for m in pc.MODELS for ins in pc.INSTRUCTIONS for run in pc.RUNS]


class SampleTests(unittest.TestCase):
    def test_margins_and_determinism(self):
        recs = synthetic_records()
        items, info = draw(recs, 100, SEED)
        self.assertEqual(len(items), 100)
        self.assertEqual(len({(x["case"], x["label"]) for x in items}), 100)
        self.assertEqual(sorted(Counter(info["per_stratum"].values()).items()), [(8, 8), (9, 4)])
        self.assertEqual(sorted(Counter(info["per_case"].values()).items()), [(5, 14), (6, 5)])
        cells = Counter((x["case"], x["evidence"], x["model"]) for x in items)
        self.assertEqual(max(cells.values()), 1)
        self.assertEqual(sorted(info["per_instruction"].values()), [33, 33, 34])
        random.Random(1).shuffle(recs)
        self.assertEqual(draw(recs, 100, SEED)[0], items)  # order of the records does not matter
        self.assertNotEqual(draw(recs, 100, SEED + 1)[0], items)

    def test_independent_of_hash_seed(self):
        code = ("import sys, json; sys.path.insert(0, %r); import judge_compare_sample as m; "
                "print(json.dumps(m.draw(m.synthetic_records())[0]))") % str(Path(__file__).resolve().parent)
        outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                               env={**os.environ, "PYTHONHASHSEED": h}).stdout for h in ("0", "1", "12345")}
        self.assertEqual(len(outs), 1)


class ReportTests(unittest.TestCase):
    def test_kappa_values_and_pairs(self):
        self.assertAlmostEqual(ja.cohen([True, True, False, False], [True, False, False, False], [False, True]), 0.5)
        items, _ = draw(synthetic_records(), 100, SEED)
        sample = {"items": items, "seed": SEED}

        def row(it, flip=False):
            r = {**plain_row(it["label"]), "output_sha": it["output_sha"], "judge_model": "x"}
            if flip:
                r["damaged"] = not r["damaged"]
            return [r]
        pilot = {**{jp.result_key("astra", it): row(it) for it in items},
                 **{jp.result_key("sol", it): row(it, flip=i % 4 == 0) for i, it in enumerate(items)}}
        comp = {**{jp.result_key("gemini-pro", it): row(it) for it in items},
                **{jp.result_key("gemini-flash", it): row(it, flip=i % 2 == 0) for i, it in enumerate(items[:80])}}
        comp[jp.result_key("gemini-pro", items[0])][0]["output_sha"] = "stale"
        rows, stale = load_rows(sample, pilot, comp)
        self.assertEqual(stale, {"gemini-pro": 1})
        s = compare(sample, rows)
        self.assertEqual(s["judged"], {"astra": 100, "sol": 100, "gemini-pro": 99, "gemini-flash": 80})
        d = s["pairs"]["astra-gemini-pro"]
        self.assertEqual(d["n"], 99)
        for lab in ("addressed", "code_consistent", "invented", "damaged", "complete"):
            self.assertEqual((d[lab]["raw"], d[lab]["kappa"]), (1.0, 1.0), lab)
        self.assertEqual(s["pairs"]["astra-gemini-flash"]["damaged"]["raw"], 0.5)
        self.assertEqual(s["pairs"]["astra-sol"]["damaged"]["raw"], 0.75)
        self.assertIn("gemini-pro-gemini-flash", s["pairs"])
        self.assertEqual(s["complete_kappa_ci"]["astra-gemini-pro"], [1.0, 1.0])
        self.assertEqual(s["complete_kappa_difference"]["astra: gemini-pro - gemini-flash"]["n"], 79)


DATA_FILES = (jp.RECORDS, jp.OUT, jp.USAGE, jp.EXCLUDED, pc.CASES_FILE)


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


@unittest.skipUnless(all(p.exists() for p in DATA_FILES), "pilot data not present")
class EndToEnd(unittest.TestCase):
    """judge_pilot.py on the real sample against the fake API, where gemini-pro answers with
    Astra's pilot labels and gemini-flash with Sol's, so the report must show kappa 1 for those
    pairs. The pilot files must be byte-identical afterwards."""

    def test_run_and_report(self):
        before = {str(p): sha(p) for p in DATA_FILES}
        pilot = json.loads(jp.OUT.read_text())
        by_label = {}
        for k, v in pilot.items():
            judge, rest = k.split(":", 1)
            by_label[(judge, rest.rsplit("/", 1)[1])] = v[0]
        src = {jp.GEMINI_MODELS["gemini-pro"]: "astra", jp.GEMINI_MODELS["gemini-flash"]: "sol"}
        fake = FakeGemini(lambda model, label: {k: by_label[(src[model], label)][k] for k in jp.LABELS})
        try:
            with tempfile.TemporaryDirectory() as d:
                d = Path(d)
                records, excluded, digest = pool()
                items, info = draw(records)
                (d / "sample.json").write_text(json.dumps({**info, "items": items}))
                env = {**os.environ, "GEMINI_API_BASE": fake.base, "GEMINI_API_KEY": KEY,
                       "GEMINI_ENV_FILE": str(d / "no-such.env"), "PILOT_ROOT": str(d / "pilot"),
                       "no_proxy": "127.0.0.1,localhost", "NO_PROXY": "127.0.0.1,localhost"}
                (d / "pilot").mkdir()
                cmd = [sys.executable, str(Path(jp.__file__)), "--judges", "gemini-pro,gemini-flash",
                       "--sample", str(d / "sample.json"), "--out", str(d / "judgments.json"), "--workers", "4"]
                dry = subprocess.run(cmd + ["--dry-run"], env=env, capture_output=True, text=True)
                self.assertEqual(dry.returncode, 0, dry.stderr)
                n_prompts = int(re.search(r"in (\d+) prompts per judge", dry.stdout).group(1))
                self.assertEqual(fake.requests, [])
                run = subprocess.run(cmd, env=env, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-2000:])
                self.assertNotIn(KEY, run.stdout + run.stderr)
                self.assertEqual(len(fake.requests), 2 * n_prompts)
                judged = json.loads((d / "judgments.json").read_text())
                self.assertEqual(Counter(k.split(":")[0] for k in judged), {"gemini-pro": 100, "gemini-flash": 100})
                usage = usage_rows(d / "judge-usage.jsonl")
                self.assertEqual(len(usage), 2 * n_prompts)
                self.assertTrue(all(u["outcome"] == "complete" and u["thinking_level"] == "high" for u in usage))
                self.assertTrue((d / "judgments.excluded.json").exists())
                o = argparse.Namespace(sample=d / "sample.json", pilot_judgments=jp.OUT, judgments=d / "judgments.json",
                                       usage=d / "judge-usage.jsonl", out=d / "agreement.json")
                with contextlib.redirect_stdout(io.StringIO()):
                    s = cmd_report(o)
                for lab in ja.LABELS:
                    for pair in ("astra-gemini-pro", "sol-gemini-flash"):
                        self.assertEqual(s["pairs"][pair][lab]["raw"], 1.0, (pair, lab))
                    self.assertEqual(s["pairs"]["astra-gemini-flash"][lab], s["pairs"]["astra-sol"][lab], lab)
                self.assertNotIn(KEY, "".join(p.read_text() for p in d.glob("*.json*")))
        finally:
            fake.close()
        self.assertEqual(before, {str(p): sha(p) for p in DATA_FILES}, "a pilot file changed")


def cmd_selftest(o) -> None:
    os.environ["GEMINI_ENV_FILE"] = str(Path(tempfile.gettempdir()) / "judge-compare-selftest-no-such.env")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(t)
                               for t in (KeyTests, CallTests, SampleTests, ReportTests, EndToEnd))
    res = unittest.TextTestRunner(verbosity=2 if o.verbose else 1).run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--seed", type=int, default=SEED)
    s.add_argument("--n", type=int, default=N)
    s.add_argument("--dry-run", action="store_true", help="print the margins without writing the sample")
    s.add_argument("--force", action="store_true", help="replace an existing, different sample")
    r = sub.add_parser("report")
    r.add_argument("--sample", type=Path, default=SAMPLE)
    r.add_argument("--pilot-judgments", type=Path, default=jp.OUT)
    r.add_argument("--judgments", type=Path, default=JUDGMENTS)
    r.add_argument("--usage", type=Path, default=USAGE)
    r.add_argument("--out", type=Path, default=REPORT)
    t = sub.add_parser("selftest")
    t.add_argument("-v", "--verbose", action="store_true")
    o = ap.parse_args()
    {"sample": cmd_sample, "report": cmd_report, "selftest": cmd_selftest}[o.cmd](o)


if __name__ == "__main__":
    main()
