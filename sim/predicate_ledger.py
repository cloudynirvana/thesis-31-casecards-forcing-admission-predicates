#!/usr/bin/env python3
"""CaseCard predicate ledger for tip-ODE forcing admission.

The legal card is the specification. Checks are read from that file.
Kinetic Θ is a separate object and is never assigned from card prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parent
CARD_PATH = ROOT / "cards" / "cc_tip_admission.json"
LEAF_PATH = ROOT / "cards" / "cc_poison_leaf.json"
PROSE_PATH = ROOT / "cards" / "cc_poison_prose.json"
CLAIMS_PATH = ROOT / "claims.json"
FIG_DIR = ROOT / "figures"
RESULTS_PATH = ROOT / "results.json"

# SHA-256 of the files as stored in this deposit. A byte edit that does not
# update the pin raises before any call is issued.
CARD_PIN = "9107ac051afa431e574da424a051af94d03c7d148679d9bd23d7d2b23b97fae6"
CLAIMS_PIN = "ac1afc2410a64ab9919bac96027efe4a7dfff023fdaa5e75aa3ceb5f06238eed"
LEAF_PIN = "4fbf502fc8bdd31df1e8ee6c974a22911cfd5b01671c9243f03377ecdb7e99ef"
PROSE_PIN = "a2ddeaedca9e34d11de4fe88cd573586337527af1e2ff4019aacab98c397fc57"

# The numeral lives here, not on the card and not in Θ.
# The card may name the token. It may not introduce a new token.
PROTOCOL_TABLE = {"unit_schedule": "1"}

THETA = {
    "u_in": "0.40",
    "k_glyc": "0.80",
    "g": "0.25",
    "d0": "0.20",
    "d_u": "0.30",
    "s": "0.50",
}

Y0 = {"G": "1", "R": "0.25", "A": "0.60"}
T_END = 40.0
N_NODES = 401
RTOL = 1e-8
ATOL = 1e-11

ANECDOTE = "An unpublished note said a coordinate moved."
PARSED_NUMERAL = "0.42"

DOSE_RE = re.compile(r"(?i)\b\d+(?:\.\d+)?\s*(?:mg|ug|µg|g|ml|mmol)\s*/\s*kg\b")
SCHEDULE_RE = re.compile(r"(?i)\bq\d+w\b")
PK_RE = re.compile(r"(?i)\b(?:ec50|ic50|ed50)\b")
NUM_RE = re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?")

REQUIRED_DISCLAIMER = (
    "not a medical device",
    "not dosing",
    "not a cure",
    "not clinical decision support",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj) -> str:
    return sha256_bytes(canon(obj).encode("utf-8"))


def load_pinned(path: Path, pin: str):
    raw = path.read_bytes()
    got = sha256_bytes(raw)
    if got != pin:
        raise SystemExit(f"pin mismatch for {path.name}: {got}")
    return json.loads(raw.decode("utf-8")), raw


def walk_leaves(obj, prefix="$"):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from walk_leaves(value, f"{prefix}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from walk_leaves(value, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def screen_object(obj) -> list[str]:
    """Card-layer refusal. Booleans are flags. JSON numbers are leaves."""
    reasons: list[str] = []
    for _path, value in walk_leaves(obj):
        if isinstance(value, bool):
            reasons.append("boolean_leaf")
        elif isinstance(value, (int, float)):
            reasons.append("numeric_leaf")
        elif isinstance(value, str):
            if DOSE_RE.search(value):
                reasons.append("dose_token")
            if SCHEDULE_RE.search(value):
                reasons.append("schedule_token")
            if PK_RE.search(value):
                reasons.append("pk_token")
            if NUM_RE.search(value):
                reasons.append("numeric_token_in_prose")
        elif value is None:
            reasons.append("null_leaf")
        else:
            reasons.append("unsupported_leaf")
    ordered = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return ordered


def collect_prose(card: dict) -> list[str]:
    found: list[str] = []

    def add(text: str) -> None:
        if text and text not in found:
            found.append(text)

    add(card["disease"]["name"])
    add(card["disease"]["framing"])
    add(card["disclaimer"])
    for item in card["nstg_touchpoints"]:
        add(item["constraint_statement"])
    for item in card["observables"]:
        add(item["statement"])
    for item in card["candidate_mechanisms"]:
        add(item["statement"])
    for item in card["falsifiers"]:
        add(item["if_observed"])
        add(item["then_reject"])
    return found


def validate_legal_card(card: dict, raw: bytes) -> None:
    text = raw.decode("utf-8")
    if any(ch.isdigit() for ch in text):
        raise SystemExit("legal card contains a digit")
    if screen_object(card):
        raise SystemExit(f"legal card failed the loader: {screen_object(card)}")
    disclaimer = card["disclaimer"].lower()
    for phrase in REQUIRED_DISCLAIMER:
        if phrase not in disclaimer:
            raise SystemExit(f"disclaimer missing {phrase!r}")
    for touch in card["nstg_touchpoints"]:
        if touch["role"] != "constraint":
            raise SystemExit("touchpoint role is not constraint")
    for mech in card["candidate_mechanisms"]:
        if mech["status"] != "hypothesis":
            raise SystemExit("mechanism status is not hypothesis")
    if card["protocol"]["amplitude_token"] not in PROTOCOL_TABLE:
        raise SystemExit("card named an amplitude token the ledger does not hold")
    reasons = [item["reason"] for item in card["predicates"]]
    if len(reasons) != len(set(reasons)):
        raise SystemExit("predicate reasons are not unique")
    if card["predicates"][-1]["check"] != "slot":
        raise SystemExit("slot check is not last")
    dest = next(item for item in card["predicates"] if item["check"] == "destination")
    rule = next(item for item in card["predicates"] if item["check"] == "amplitude_rule")
    if dest["expect"] != card["protocol"]["destination_symbol"]:
        raise SystemExit("destination predicate drifted from the protocol block")
    if rule["expect"] != card["protocol"]["amplitude_rule"]:
        raise SystemExit("amplitude predicate drifted from the protocol block")
    known = {
        "kind",
        "kind_not",
        "rule_not",
        "destination_not_in",
        "destination",
        "library_sha",
        "engine",
        "may_enter_theta",
        "claim_token",
        "pains_token",
        "unit",
        "amplitude_rule",
        "prose_absent",
        "provenance_note",
        "slot",
    }
    used = {item["check"] for item in card["predicates"]}
    if not used <= known:
        raise SystemExit(f"card uses an unknown check: {used - known}")


def theta_floats() -> dict[str, float]:
    return {key: float(Decimal(value)) for key, value in THETA.items()}


def null_forcing() -> dict:
    return {
        "symbol": "u_phyto",
        "amplitude": "0",
        "amplitude_rule": "null_schedule",
        "amplitude_token": None,
        "provenance": None,
    }


def admitted_forcing(card: dict, row: dict) -> dict:
    token = card["protocol"]["amplitude_token"]
    return {
        "symbol": card["protocol"]["destination_symbol"],
        "amplitude": PROTOCOL_TABLE[token],
        "amplitude_rule": card["protocol"]["amplitude_rule"],
        "amplitude_token": token,
        "provenance": {
            "card_id": card["card_id"],
            "row_id": row["id"],
            "claim_token": row["claim_token"],
            "pains_token": row["pains_token"],
            "library_pin": CARD_PIN,
            "score_copied": False,
            "guideline_text_copied": False,
        },
    }


class Ledger:
    def __init__(self, card: dict, prose: list[str], rows: dict[str, dict]):
        self.card = card
        self.prose = prose
        self.rows = rows
        self.forcing = null_forcing()
        self.occupied = False
        self.theta_baseline = canon(THETA)
        self.predicates = card["predicates"]

    def _row(self, call: dict):
        row_id = call.get("row_id")
        if row_id is None:
            return None
        return self.rows.get(row_id)

    def _passes(self, pred: dict, call: dict) -> bool:
        check = pred["check"]
        expect = pred["expect"]
        kind = call["kind"]
        if check == "kind":
            return kind == expect
        if check == "kind_not":
            return kind != expect
        if check == "rule_not":
            return call["amplitude_rule"] != expect
        if check == "destination_not_in":
            if expect != "theta":
                raise SystemExit(f"unsupported destination set {expect}")
            return call["destination"] not in THETA
        if check == "destination":
            return call["destination"] == expect
        if check == "library_sha":
            if expect != "pin":
                raise SystemExit("library check must point at the card pin")
            return call["library_sha"] == CARD_PIN
        if check == "engine":
            if expect != "null":
                raise SystemExit("engine check must expect null")
            return call["engine"] is None
        if check == "may_enter_theta":
            if expect != "false":
                raise SystemExit("may_enter_theta check must expect false")
            return call["may_enter_theta"] is False
        if check in {"claim_token", "pains_token"}:
            if kind != "score_record":
                return True
            row = self._row(call)
            if row is None:
                return False
            return row[check] == expect
        if check == "unit":
            if kind != "score_record":
                return True
            row = self._row(call)
            if row is None:
                return False
            unit = call["unit_override"] if call.get("unit_override") else row["unit"]
            return unit == expect
        if check == "amplitude_rule":
            return call["amplitude_rule"] == expect
        if check == "prose_absent":
            payload = call.get("payload") or ""
            return not any(piece and piece in payload for piece in self.prose)
        if check == "provenance_note":
            if expect != "empty":
                raise SystemExit("provenance check must expect empty")
            return not call.get("provenance_note")
        if check == "slot":
            raise SystemExit("slot is applied after the other checks")
        raise SystemExit(f"unknown check {check}")

    def evaluate(self, call: dict) -> list[str]:
        failures: list[str] = []
        for pred in self.predicates:
            if pred["check"] == "slot":
                continue
            if not self._passes(pred, call):
                reason = pred["reason"]
                if reason not in failures:
                    failures.append(reason)
        if not failures:
            slot = self.predicates[-1]
            if slot["expect"] != "empty":
                raise SystemExit("slot expect drifted")
            if self.occupied:
                failures.append(slot["reason"])
        return failures

    def issue(self, call_id: str, call: dict) -> dict:
        reasons = self.evaluate(call)
        status = "refused" if reasons else "admitted"
        if status == "admitted":
            row = self._row(call)
            if row is None:
                raise SystemExit("admission without a row")
            self.forcing = admitted_forcing(self.card, row)
            self.occupied = True
        if canon(THETA) != self.theta_baseline:
            raise SystemExit(f"theta moved on {call_id}")
        return {
            "call_id": call_id,
            "row_id": call.get("row_id"),
            "kind": call["kind"],
            "destination": call["destination"],
            "amplitude_rule": call["amplitude_rule"],
            "status": status,
            "reasons": reasons,
            "theta_unchanged": True,
            "forcing_digest": digest(self.forcing),
        }


def base_call(**overrides) -> dict:
    call = {
        "kind": "score_record",
        "amplitude_rule": "protocol_constant",
        "destination": "u_phyto",
        "library_sha": CARD_PIN,
        "engine": None,
        "may_enter_theta": False,
        "row_id": "row_north",
        "payload": "unit_schedule",
        "provenance_note": None,
    }
    call.update(overrides)
    return call


def eligibility(ledger: Ledger, row_id: str) -> dict:
    call = base_call(row_id=row_id)
    # Eligibility is the predicate with an empty slot. Drop the side score
    # before the call is built so the column cannot become an input.
    row = dict(ledger.rows[row_id])
    row.pop("side_score", None)
    reasons = ledger.evaluate(call)
    return {
        "id": row_id,
        "label": row["label"],
        "claim_token": row["claim_token"],
        "pains_token": row["pains_token"],
        "eligible": reasons == [],
        "reasons": reasons,
    }


def rhs(t: float, y: np.ndarray, u: float, p: dict[str, float]):
    g_state, r_state, a_state = y
    dG = p["u_in"] - p["k_glyc"] * g_state
    dR = p["g"] * p["k_glyc"] * g_state - (p["d0"] + p["d_u"] * u) * r_state
    dA = p["k_glyc"] * g_state / (1.0 + r_state) - p["s"] * a_state
    return (dG, dR, dA)


def closed_form(t: np.ndarray, u: float, p: dict[str, float], y0: np.ndarray):
    k = p["k_glyc"]
    g_star = p["u_in"] / k
    g = g_star + (y0[0] - g_star) * np.exp(-k * t)
    a_clear = p["d0"] + p["d_u"] * u
    b = p["g"] * k
    r_star = b * g_star / a_clear
    c2 = b * (y0[0] - g_star) / (a_clear - k)
    c1 = y0[1] - r_star - c2
    r = r_star + c1 * np.exp(-a_clear * t) + c2 * np.exp(-k * t)
    return g, r


def equilibria(u: float, p: dict[str, float]) -> dict[str, float]:
    g_star = p["u_in"] / p["k_glyc"]
    r_star = p["g"] * p["u_in"] / (p["d0"] + p["d_u"] * u)
    a_star = p["u_in"] / (p["s"] * (1.0 + r_star))
    return {"G": g_star, "R": r_star, "A": a_star}


def integrate(u: float, p: dict[str, float], y0: np.ndarray, t: np.ndarray):
    sol = solve_ivp(
        lambda tt, yy: rhs(tt, yy, u, p),
        (float(t[0]), float(t[-1])),
        y0,
        method="LSODA",
        t_eval=t,
        rtol=RTOL,
        atol=ATOL,
    )
    if not sol.success or sol.y.shape[1] != len(t):
        raise SystemExit(f"integration failed for u={u}: {sol.message}")
    g_hat, r_hat = closed_form(t, u, p, y0)
    g_gap = float(np.max(np.abs(sol.y[0] - g_hat)))
    r_gap = float(np.max(np.abs(sol.y[1] - r_hat)))
    if g_gap > 1e-7 or r_gap > 1e-7:
        raise SystemExit(f"closed form gap too large at u={u}: G {g_gap}, R {r_gap}")
    return sol.y, {"G": g_gap, "R": r_gap}


def state_digest(t: np.ndarray, y: np.ndarray) -> str:
    rows = []
    for i in range(len(t)):
        rows.append(
            [
                round(float(t[i]), 10),
                round(float(y[0, i]), 12),
                round(float(y[1, i]), 12),
                round(float(y[2, i]), 12),
            ]
        )
    return digest(rows)


def sample_rows(t: np.ndarray, y: np.ndarray, times: list[float]) -> list[dict]:
    out = []
    for mark in times:
        idx = int(np.where(np.isclose(t, mark))[0][0])
        out.append(
            {
                "t": mark,
                "G": round(float(y[0, idx]), 6),
                "R": round(float(y[1, idx]), 6),
                "A": round(float(y[2, idx]), 6),
            }
        )
    return out


def style_axes() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 140,
            "savefig.dpi": 160,
            "axes.labelsize": 10,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
        }
    )


def plot_eligibility(rows: list[dict], path: Path) -> None:
    labels = [row["label"] for row in rows]
    heights = [1 if row["eligible"] else 0 for row in rows]
    colors = ["#1f4e79" if flag else "#c5c5c5" for flag in heights]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(labels, heights, color=colors, width=0.72)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Eligible under the card predicate")
    ax.set_yticks([0, 1])
    ax.set_xlabel("Declared row")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_digests(calls: list[dict], null_digest: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    xs = np.arange(len(calls))
    for i, rec in enumerate(calls):
        ax.scatter(i, 1.0, s=32, c="#1f4e79", marker="o", zorder=3)
        wrote = rec["forcing_digest"] != null_digest
        ax.scatter(
            i,
            0.0,
            s=32,
            c="#a33b32" if wrote else "#c5c5c5",
            marker="s",
            zorder=3,
        )
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["forcing write", "Θ unchanged"])
    ax.set_xticks(xs)
    ax.set_xticklabels([rec["call_id"] for rec in calls], rotation=90)
    ax.set_xlim(-0.6, len(calls) - 0.4)
    ax.set_ylim(-0.45, 1.45)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_trajectories(
    t: np.ndarray,
    null_y: np.ndarray,
    adm_y: np.ndarray,
    copy_y: np.ndarray,
    path: Path,
) -> None:
    series = (
        ("Glucose-like G", 0),
        ("Stress-like R", 1),
        ("ATP-like A", 2),
    )
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.4), sharex=True)
    for ax, (label, idx) in zip(axes, series):
        ax.plot(t, null_y[idx], color="#6e6e6e", lw=1.6, label="null schedule")
        ax.plot(t, adm_y[idx], color="#1f4e79", lw=1.6, label="admitted schedule")
        ax.plot(
            t,
            copy_y[idx],
            color="#a33b32",
            lw=1.1,
            ls=":",
            label="score-copy amplitude, not admitted",
        )
        ax.set_ylabel(label)
    axes[0].legend(frameon=False, fontsize=8, loc="best")
    axes[-1].set_xlabel("Toy time")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_equilibria(p: dict[str, float], copy_u: float, path: Path) -> None:
    grid = np.linspace(0.0, 2.0, 201)
    r_vals = np.array([equilibria(float(u), p)["R"] for u in grid])
    a_vals = np.array([equilibria(float(u), p)["A"] for u in grid])
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(grid, r_vals, color="#1f4e79", lw=1.7, label="R*")
    ax.plot(grid, a_vals, color="#2f6f4e", lw=1.7, label="A*")
    ax.axvline(1.0, color="#1f4e79", lw=0.8, ls="--")
    copy_r = equilibria(copy_u, p)["R"]
    ax.scatter([copy_u], [copy_r], c="#a33b32", s=36, zorder=3, label="score-copy u, not admitted")
    ax.set_xlabel("Constant forcing amplitude")
    ax.set_ylabel("Equilibrium")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def six(value: float) -> float:
    return float(f"{value:.6f}")


def main() -> None:
    style_axes()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    card, card_raw = load_pinned(CARD_PATH, CARD_PIN)
    claims, _claims_raw = load_pinned(CLAIMS_PATH, CLAIMS_PIN)
    leaf, _leaf_raw = load_pinned(LEAF_PATH, LEAF_PIN)
    prose_card, _prose_raw = load_pinned(PROSE_PATH, PROSE_PIN)
    validate_legal_card(card, card_raw)

    card_refusals = [
        {
            "fixture": "cc_poison_leaf",
            "status": "refused",
            "layer": "card_loader",
            "reasons": screen_object(leaf),
        },
        {
            "fixture": "cc_poison_prose",
            "status": "refused",
            "layer": "card_loader",
            "reasons": screen_object(prose_card),
        },
    ]
    for item in card_refusals:
        if not item["reasons"]:
            raise SystemExit(f"{item['fixture']} was accepted")

    rows = {row["id"]: row for row in claims["rows"]}
    if any("side_score" in row for row in rows.values() if row["id"] != "row_north"):
        raise SystemExit("side score leaked onto a row that should not carry one")
    side_score = rows["row_north"]["side_score"]
    if side_score.encode("utf-8") in card_raw:
        raise SystemExit("side score appears on the legal card")

    prose = collect_prose(card)
    constraint = card["nstg_touchpoints"][0]["constraint_statement"]
    framing = card["disease"]["framing"]
    ledger = Ledger(card, prose, rows)

    elig = [eligibility(ledger, row["id"]) for row in claims["rows"]]
    if ledger.occupied:
        raise SystemExit("eligibility occupied the slot")

    flipped = CARD_PIN[:-1] + ("0" if CARD_PIN[-1] != "0" else "1")
    planned = [
        ("R01", base_call(kind="guideline_text", amplitude_rule="guideline_prose", destination="d0", row_id=None, payload=constraint)),
        ("R02", base_call(kind="knowledge_text", amplitude_rule="knowledge_prose", destination="k_glyc", row_id=None, payload=framing)),
        ("R03", base_call(kind="parsed_numeral", amplitude_rule="parsed_guideline_numeral", destination="d0", row_id=None, payload=PARSED_NUMERAL)),
        ("R04", base_call(kind="guideline_text", amplitude_rule="guideline_prose", destination="u_phyto", row_id=None, payload=constraint)),
        ("R05", base_call(amplitude_rule="copy_score", payload=side_score)),
        ("R06", base_call(amplitude_rule="soft_prior", destination="d0")),
        ("R07", base_call(kind="anecdote", row_id=None, payload=ANECDOTE)),
        ("R08", base_call(row_id="row_east")),
        ("R09", base_call(row_id="row_south")),
        ("R10", base_call(engine="vina")),
        ("R11", base_call(may_enter_theta=True)),
        ("R12", base_call(library_sha=flipped)),
        ("R13", base_call(kind="utility", amplitude_rule="copy_score", destination="g", payload="utility")),
        ("R14", base_call(destination="N_ROS")),
        ("R15", base_call(provenance_note=constraint)),
        ("A01", base_call()),
        ("R16", base_call(row_id="row_west")),
        ("R17", base_call(amplitude_rule="copy_score", payload=side_score)),
        ("R18", base_call(amplitude_rule="soft_weight", destination="s")),
        ("R19", base_call(unit_override="mg_per_kg")),
    ]

    null_digest = digest(ledger.forcing)
    theta_before = digest(THETA)
    calls = []
    for call_id, call in planned:
        before = digest(ledger.forcing)
        rec = ledger.issue(call_id, call)
        rec["forcing_changed"] = rec["forcing_digest"] != before
        calls.append(rec)
    theta_after = digest(THETA)
    if theta_before != theta_after:
        raise SystemExit("theta digest changed across the run")
    if canon(THETA) != ledger.theta_baseline:
        raise SystemExit("theta bytes changed across the run")

    admitted = [rec for rec in calls if rec["status"] == "admitted"]
    if [rec["call_id"] for rec in admitted] != ["A01"]:
        raise SystemExit(f"admission set is {admitted}")
    seen_admission = False
    for rec in calls:
        if rec["call_id"] == "A01":
            seen_admission = True
            if rec["status"] != "admitted" or rec["forcing_digest"] == null_digest:
                raise SystemExit("A01 did not write the forcing")
            continue
        if rec["status"] != "refused":
            raise SystemExit(f"unexpected admission on {rec['call_id']}")
        expected = digest(ledger.forcing) if seen_admission else null_digest
        if rec["forcing_digest"] != expected:
            raise SystemExit(f"{rec['call_id']} disturbed the forcing digest")

    admitted_blob = canon(ledger.forcing)
    for piece in prose:
        if piece in admitted_blob:
            raise SystemExit("card prose entered the admitted forcing")
    if side_score in admitted_blob or PARSED_NUMERAL in admitted_blob or ANECDOTE in admitted_blob:
        raise SystemExit("a refused numeral or anecdote entered the admitted forcing")
    if constraint in canon(THETA) or framing in canon(THETA):
        raise SystemExit("card prose entered theta")

    # Contrasts that are computed and not assigned.
    s_side = Decimal(side_score)
    prior_mean = Decimal(THETA["d0"]) + Decimal("0.02") * (-s_side)
    posterior = (prior_mean + Decimal(THETA["d0"])) / Decimal(2)
    prior_s = format(prior_mean, "f")
    post_s = format(posterior, "f")
    counterfactual = dict(THETA)
    counterfactual["d0"] = post_s
    counter_digest = digest(counterfactual)
    if counter_digest == theta_before:
        raise SystemExit("soft prior did not change the counterfactual digest")
    if digest(THETA) != theta_before:
        raise SystemExit("soft prior was written")

    p = theta_floats()
    y0 = np.array([float(Decimal(Y0["G"])), float(Decimal(Y0["R"])), float(Decimal(Y0["A"]))], dtype=float)
    t = np.linspace(0.0, T_END, N_NODES)
    u_admitted = float(Decimal(ledger.forcing["amplitude"]))
    u_copy = float(-s_side)
    u_affine = float(Decimal("0.20") + Decimal("0.50") * (-s_side))
    null_y, null_gap = integrate(0.0, p, y0, t)
    adm_y, adm_gap = integrate(u_admitted, p, y0, t)
    copy_y, copy_gap = integrate(u_copy, p, y0, t)
    affine_y, affine_gap = integrate(u_affine, p, y0, t)

    g_gap = float(np.max(np.abs(null_y[0] - adm_y[0])))
    if g_gap > 1e-8:
        raise SystemExit(f"glucose paths separated: {g_gap}")
    state_gap = float(np.max(np.abs(null_y - adm_y)))
    null_state = state_digest(t, null_y)
    adm_state = state_digest(t, adm_y)
    if null_state == adm_state:
        raise SystemExit("state digests failed to separate")

    eq_null = equilibria(0.0, p)
    eq_adm = equilibria(u_admitted, p)
    if abs(eq_null["G"] - eq_adm["G"]) > 1e-12:
        raise SystemExit("G* depends on the forcing")

    times = [0.0, 5.0, 10.0, 20.0, 40.0]
    samples = {
        "null": sample_rows(t, null_y, times),
        "admitted": sample_rows(t, adm_y, times),
        "score_copy_not_admitted": sample_rows(t, copy_y, times),
        "affine_not_admitted": sample_rows(t, affine_y, times),
    }

    def terminal_gap(y: np.ndarray, eq: dict[str, float], key: str, idx: int) -> float:
        return abs(float(y[idx, -1]) - eq[key])

    plot_eligibility(elig, FIG_DIR / "eligibility.png")
    plot_digests(calls, null_digest, FIG_DIR / "digest_stability.png")
    plot_trajectories(t, null_y, adm_y, copy_y, FIG_DIR / "trajectories.png")
    plot_equilibria(p, u_copy, FIG_DIR / "equilibria.png")

    eligible_ids = [row["id"] for row in elig if row["eligible"]]
    if eligible_ids != ["row_north", "row_west"]:
        raise SystemExit(f"eligible set {eligible_ids}")

    results = {
        "rng_draws": 0,
        "card_pin": CARD_PIN,
        "claims_pin": CLAIMS_PIN,
        "poison_leaf_pin": LEAF_PIN,
        "poison_prose_pin": PROSE_PIN,
        "protocol_table_sha256": digest(PROTOCOL_TABLE),
        "protocol_table": PROTOCOL_TABLE,
        "theta": THETA,
        "theta_sha256": theta_before,
        "theta_sha256_after": theta_after,
        "theta_bytes_unchanged": canon(THETA) == ledger.theta_baseline,
        "null_forcing_sha256": null_digest,
        "admitted_forcing_sha256": digest(ledger.forcing),
        "admitted_forcing": ledger.forcing,
        "y0": Y0,
        "horizon": [0, T_END],
        "n_nodes": N_NODES,
        "rtol": RTOL,
        "atol": ATOL,
        "card_loader_refusals": card_refusals,
        "eligibility": elig,
        "calls": calls,
        "n_calls": len(calls),
        "n_admitted": len(admitted),
        "n_refused": sum(rec["status"] == "refused" for rec in calls),
        "legal_card_digit_count": 0,
        "side_score_on_card": False,
        "equilibria": {
            "null": {key: six(value) for key, value in eq_null.items()},
            "admitted": {key: six(value) for key, value in eq_adm.items()},
        },
        "terminal_gaps": {
            "null_R": terminal_gap(null_y, eq_null, "R", 1),
            "null_A": terminal_gap(null_y, eq_null, "A", 2),
            "admitted_R": terminal_gap(adm_y, eq_adm, "R", 1),
            "admitted_A": terminal_gap(adm_y, eq_adm, "A", 2),
        },
        "closed_form_gaps": {"null": null_gap, "admitted": adm_gap, "score_copy": copy_gap, "affine": affine_gap},
        "g_path_gap_null_vs_admitted": g_gap,
        "state_gap_null_vs_admitted": state_gap,
        "null_state_sha256": null_state,
        "admitted_state_sha256": adm_state,
        "samples": samples,
        "contrasts": {
            "side_score": side_score,
            "soft_prior_mean_d0": prior_s,
            "soft_prior_posterior_d0": post_s,
            "soft_prior_theta_sha256": counter_digest,
            "soft_prior_written_to_ledger_theta": False,
            "score_copy_amplitude": format(-s_side, "f"),
            "affine_amplitude": format(Decimal("0.20") + Decimal("0.50") * (-s_side), "f"),
            "parsed_numeral_not_written": PARSED_NUMERAL,
            "anecdote": ANECDOTE,
            "anecdote_recomputed": False,
        },
        "predicate_reasons_in_card_order": [item["reason"] for item in card["predicates"]],
        "constraint_statement": constraint,
        "framing": framing,
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    print(f"theta {theta_before}")
    print(f"null forcing {null_digest}")
    print(f"admitted forcing {digest(ledger.forcing)}")
    print(f"protocol table {digest(PROTOCOL_TABLE)}")
    print(f"calls {len(calls)} admitted {len(admitted)} refused {results['n_refused']}")
    print("eligibility", [(row["id"], row["eligible"], row["reasons"]) for row in elig])
    for rec in calls:
        print(f"{rec['call_id']:4} {rec['status']:8} {rec['reasons']}")
    print("card refusals", card_refusals)
    print("eq", results["equilibria"])
    print("gaps", results["terminal_gaps"])
    print("g path", g_gap, "state", state_gap)
    print("closed", results["closed_form_gaps"])
    print("contrasts", results["contrasts"])
    print("state digests", null_state, adm_state)
    print("samples null", samples["null"])
    print("samples adm", samples["admitted"])
    print("wrote", RESULTS_PATH)


if __name__ == "__main__":
    main()
