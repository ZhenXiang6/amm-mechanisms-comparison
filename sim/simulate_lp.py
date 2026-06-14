"""
simulate_lp.py — Monte-Carlo simulation of LP profitability (LP value vs HODL)
for different AMM designs under varying VOLATILITY and trading-VOLUME scenarios.

Model
-----
* The risky asset X follows a geometric Brownian motion (GBM) vs the numeraire Y.
* Arbitrageurs continuously keep each pool's marginal price equal to the external
  price, so a pool's reserve value is a deterministic function PV(r) of the price
  ratio r = P_t / P_0 (closed forms below).  The gap PV(r) - HODL(r) is the
  impermanent loss / divergence loss.
* Trading fees accrue daily as  fee_rate * daily_volume, with the annual volume
  set to `turnover` x TVL.  A Uniswap-V3 position concentrated in [p_a, p_b]
  earns `concentration` x the fees of a full-range position while the price is in
  range (capital efficiency) and zero fees while out of range.
* LP-vs-HODL return = (PV(r_T) + accrued_fees) / HODL(r_T) - 1.

Closed-form pool values (deposit value normalised to 1 at P_0 = 1)
    Constant-product 50/50 :  PV(r) = sqrt(r)
    Weighted  w / (1-w)     :  PV(r) = r^w
    Uniswap V3 range        :  from the virtual-reserve formulas (see code)
"""
from __future__ import annotations

import json
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams.update({
    "figure.dpi": 140, "savefig.dpi": 140, "font.size": 11,
    "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.autolayout": True,
})

OUT = os.path.join(os.path.dirname(__file__), "..", "report", "figures")
TAB = os.path.join(os.path.dirname(__file__), "..", "report")
os.makedirs(OUT, exist_ok=True)

C = {"cp": "#1f77b4", "w8020": "#d62728", "w9802": "#9467bd", "v3": "#ff7f0e"}
FEE_RATE = 0.003
T_DAYS = 365
SEED = 20240614


# ---- pool value functions, deposit normalised to 1 at P0 = 1 -------------
def pv_constant_product(r):
    return np.sqrt(r)


def pv_weighted(r, w):
    return r ** w


def _v3_xy(P, pa, pb):
    sp = np.sqrt(np.clip(P, pa, pb))
    x = 1.0 / sp - 1.0 / np.sqrt(pb)
    y = sp - np.sqrt(pa)
    return x, y


def pv_v3(r, pa, pb):
    x0, y0 = _v3_xy(1.0, pa, pb)
    v0 = x0 * 1.0 + y0                     # deposit value at P0 = 1
    x, y = _v3_xy(r, pa, pb)
    return (x * r + y) / v0                 # normalised so PV(1) = 1


def hold_value(r, w):
    """Value of holding the initial w/(1-w) value-weighted deposit at ratio r."""
    return w * r + (1.0 - w)


def v3_concentration(pa, pb):
    return 1.0 / (1.0 - (pa / pb) ** 0.25)


# ---- one Monte-Carlo scenario --------------------------------------------
def simulate(sigma_annual, turnover, n_paths=5000, seed=SEED):
    """Return dict pool -> array of LP-vs-HODL returns over n_paths."""
    rng = np.random.default_rng(seed)
    dt = 1.0 / T_DAYS
    mu = -0.5 * sigma_annual ** 2          # risk-neutral drift (martingale price)
    # daily log returns
    z = rng.standard_normal((n_paths, T_DAYS))
    log_incr = mu * dt + sigma_annual * np.sqrt(dt) * z
    log_path = np.cumsum(log_incr, axis=1)
    P = np.exp(log_path)                    # price path, P_0 = 1 -> shape (paths, T)
    P = np.concatenate([np.ones((n_paths, 1)), P], axis=1)  # include t=0
    r_T = P[:, -1]
    daily_vol_frac = turnover / T_DAYS      # daily volume as fraction of TVL

    pools = {
        "cp":    dict(w=0.5,  pv=lambda r: pv_constant_product(r),     conc=1.0, rng=None),
        "w8020": dict(w=0.8,  pv=lambda r: pv_weighted(r, 0.8),        conc=1.0, rng=None),
        "w9802": dict(w=0.98, pv=lambda r: pv_weighted(r, 0.98),       conc=1.0, rng=None),
        "v3":    dict(w=0.5,  pv=lambda r: pv_v3(r, 0.5, 2.0),         conc=v3_concentration(0.5, 2.0), rng=(0.5, 2.0)),
    }

    out = {}
    for name, cfg in pools.items():
        pv_path = cfg["pv"](P)                       # (paths, T+1) pool value
        # daily fee accrual = fee_rate * daily_volume(=turnover/365 * PV_t)
        in_range = np.ones_like(P)
        if cfg["rng"] is not None:
            pa, pb = cfg["rng"]
            in_range = ((P >= pa) & (P <= pb)).astype(float)
        fee_daily = FEE_RATE * daily_vol_frac * pv_path * cfg["conc"] * in_range
        fees = fee_daily[:, 1:].sum(axis=1)          # accrue over the year
        pv_T = cfg["pv"](r_T)
        hold_T = hold_value(r_T, cfg["w"])
        ret = (pv_T + fees) / hold_T - 1.0
        out[name] = ret
    return out, r_T


# ---- figures + table -----------------------------------------------------
def main():
    labels = {
        "cp": "Constant-product 50/50 (Uniswap V2)",
        "w8020": "Weighted 80/20 (Balancer)",
        "w9802": "Weighted 98/2 (Balancer)",
        "v3": "Uniswap V3 range [0.5, 2.0]",
    }

    # ---- Figure A: return distributions for a representative scenario ----
    sigma0, turn0 = 0.80, 50
    res, r_T = simulate(sigma0, turn0)
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    order = ["cp", "w8020", "w9802", "v3"]
    data = [res[k] * 100 for k in order]
    parts = ax.violinplot(data, showmedians=True, showextrema=False)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(C[order[i]]); pc.set_alpha(0.55)
    parts["cmedians"].set_color("k")
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([labels[k].replace(" (", "\n(") for k in order], fontsize=8.5)
    ax.set_ylabel("LP return vs HODL after 1 year  (%)")
    ax.set_title(f"LP profitability distribution\n(σ = {int(sigma0*100)}%/yr, volume = {turn0}× TVL/yr, fee = 0.30%)")
    ax.set_ylim(-40, 30)
    save(fig, "fig_mc_distributions.pdf")

    # ---- Figure B: mean net return across volatility & volume scenarios ----
    sigmas = [0.30, 0.80, 1.50]
    turns = [10, 50, 200]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))

    # left: mean return vs volatility at turnover = 50
    width = 0.2
    xs = np.arange(len(sigmas))
    for j, k in enumerate(order):
        means = [np.mean(simulate(s, 50)[0][k]) * 100 for s in sigmas]
        axL.bar(xs + (j - 1.5) * width, means, width, color=C[k], label=labels[k])
    axL.axhline(0, color="k", lw=0.8)
    axL.set_xticks(xs); axL.set_xticklabels([f"{int(s*100)}%" for s in sigmas])
    axL.set_xlabel("Annualised volatility σ")
    axL.set_ylabel("Mean LP return vs HODL  (%)")
    axL.set_title("Volume = 50× TVL/yr")
    axL.legend(fontsize=8)

    # right: P(LP beats HODL) vs volume at sigma = 80%
    xs2 = np.arange(len(turns))
    for j, k in enumerate(order):
        probs = [np.mean(simulate(0.80, t)[0][k] > 0) * 100 for t in turns]
        axR.bar(xs2 + (j - 1.5) * width, probs, width, color=C[k], label=labels[k])
    axR.set_xticks(xs2); axR.set_xticklabels([f"{t}×" for t in turns])
    axR.set_xlabel("Annual trading volume (× TVL)")
    axR.set_ylabel("P(LP beats HODL)  (%)")
    axR.set_title("σ = 80%/yr")
    axR.set_ylim(0, 100)
    save(fig, "fig_mc_scenarios.pdf")

    # ---- LaTeX results table ----
    rows = []
    for s in sigmas:
        for t in [10, 50, 200]:
            r, _ = simulate(s, t)
            rows.append((s, t,
                         np.mean(r["cp"]) * 100,
                         np.mean(r["w8020"]) * 100,
                         np.mean(r["v3"]) * 100,
                         np.mean(r["cp"] > 0) * 100))
    lines = [r"\begin{tabular}{cc|cccc}", r"\toprule",
             r"$\sigma$ (年化) & 年成交量 & \multicolumn{4}{c}{LP 相對 HODL 的平均報酬與勝率} \\",
             r" & ($\times$TVL) & 50/50 & 80/20 & V3[0.5,2] & $P(\text{50/50}{>}0)$ \\",
             r"\midrule"]
    for s, t, cp, w, v3, p in rows:
        lines.append(f"{int(s*100)}\\% & {t}$\\times$ & {cp:+.1f}\\% & {w:+.1f}\\% & {v3:+.1f}\\% & {p:.0f}\\% \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    with open(os.path.join(TAB, "tab_mc.tex"), "w") as f:
        f.write("\n".join(lines))
    print("wrote report/tab_mc.tex")

    # also dump JSON for reference
    summary = {f"sigma{int(s*100)}_turn{t}": {
        k: float(np.mean(simulate(s, t)[0][k]) * 100) for k in order
    } for s in sigmas for t in [10, 50, 200]}
    with open(os.path.join(TAB, "..", "sim", "mc_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("wrote sim/mc_summary.json")


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(path))


if __name__ == "__main__":
    main()
