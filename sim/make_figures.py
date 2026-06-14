"""
make_figures.py — generate all analytic figures for the AMM survey report.
Outputs vector PDFs into report/figures/.
"""
from __future__ import annotations

import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

from amm import (
    ConstantProduct, StableSwap, WeightedPool,
    il_constant_product, il_weighted, il_v3_range, v3_capital_efficiency,
)

mpl.rcParams.update({
    "figure.dpi": 140,
    "savefig.dpi": 140,
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "legend.fontsize": 9.5,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.autolayout": True,
})

OUT = os.path.join(os.path.dirname(__file__), "..", "report", "figures")
os.makedirs(OUT, exist_ok=True)

C_CP = "#1f77b4"   # constant product (Uniswap V2)
C_SS = "#2ca02c"   # stableswap (Curve)
C_WP = "#d62728"   # weighted (Balancer)
C_V3 = "#ff7f0e"   # Uniswap V3
C_CS = "#7f7f7f"   # constant sum


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.relpath(path))


# --------------------------------------------------------------------------
# Fig 1 — Bonding curves: how StableSwap interpolates constant-sum / product
# --------------------------------------------------------------------------
def fig_bonding_curves():
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    D = 2000.0  # invariant scale, balanced point (1000, 1000)

    x = np.linspace(20, 1980, 600)
    # constant product through (1000,1000): xy = 1e6
    ax.plot(x, 1e6 / x, color=C_CP, lw=2, label="Constant-product  $xy=k$ (Uniswap V2)")
    # constant sum through (1000,1000): x+y = 2000
    ax.plot(x, 2000 - x, color=C_CS, lw=1.6, ls="--", label="Constant-sum  $x+y=D$")

    # StableSwap for several A (solve y given x at fixed D)
    for A, shade in [(1, 0.45), (10, 0.7), (100, 1.0)]:
        ss = StableSwap(1000, 1000, A=A)
        ys = []
        for xi in x:
            try:
                ys.append(ss._y_given_x(xi, D))
            except Exception:
                ys.append(np.nan)
        ax.plot(x, ys, color=C_SS, lw=1.8, alpha=shade, label=f"StableSwap  $A={A}$ (Curve)")

    # weighted 80/20, anchored through the common (1000, 1000) point for a clean
    # shape comparison (V = 1000^0.8 * 1000^0.2 = 1000)
    V = 1000.0
    xw = np.linspace(220, 2000, 600)
    yw = (V / xw ** 0.8) ** (1 / 0.2)
    ax.plot(xw, yw, color=C_WP, lw=1.8, ls="-.", label="Weighted 80/20 (Balancer)")

    ax.scatter([1000], [1000], color="k", zorder=5, s=25)
    ax.annotate("balanced\n(1000, 1000)", (1000, 1000), textcoords="offset points",
                xytext=(12, 12), fontsize=8.5)
    ax.set_xlim(0, 2000)
    ax.set_ylim(0, 2000)
    ax.set_xlabel("Reserve of asset X")
    ax.set_ylabel("Reserve of asset Y")
    ax.set_title("AMM bonding curves: StableSwap interpolates\nconstant-sum (no slippage) and constant-product")
    ax.legend(loc="upper right", framealpha=0.9)
    save(fig, "fig_bonding_curves.pdf")


# --------------------------------------------------------------------------
# Fig 2 — Price impact vs trade size (pegged-asset scenario, all spot = 1)
# --------------------------------------------------------------------------
def fig_price_impact():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3))
    fracs = np.linspace(0.001, 0.30, 120)   # trade as fraction of X reserve
    X = 1_000_000.0

    pools = [
        ("Constant-product (Uniswap V2)", ConstantProduct(X, X, fee=0.003), C_CP, "-"),
        ("StableSwap $A=10$ (Curve)", StableSwap(X, X, A=10, fee=0.0004), C_SS, "--"),
        ("StableSwap $A=100$ (Curve)", StableSwap(X, X, A=100, fee=0.0004), C_SS, "-"),
        ("Weighted 50/50 (Balancer)", WeightedPool(X, X, wx=0.5, fee=0.003), C_WP, ":"),
        ("Weighted 80/20 (Balancer)", WeightedPool(X, X * 0.25 / 0.5 * 0.5, wx=0.8, fee=0.003), C_WP, "-."),
    ]
    # For 80/20 with spot price 1 we need y = x*wy/wx; rebuild cleanly:
    pools[4] = ("Weighted 80/20 (Balancer)", WeightedPool(X, X * 0.2 / 0.8, wx=0.8, fee=0.003), C_WP, "-.")

    for label, pool, color, ls in pools:
        imp = np.array([abs(pool.price_impact(f * pool.x)) * 100 for f in fracs])
        ax1.plot(fracs * 100, imp, color=color, ls=ls, lw=1.9, label=label)
        ax2.plot(fracs * 100, imp, color=color, ls=ls, lw=1.9, label=label)

    ax1.set_title("Price impact vs trade size (pegged pair)")
    ax1.set_xlabel("Trade size (% of X reserve)")
    ax1.set_ylabel("|Price impact|  (%)")
    ax1.legend(loc="upper left")

    ax2.set_title("Zoom: small trades (log scale)")
    ax2.set_xlabel("Trade size (% of X reserve)")
    ax2.set_ylabel("|Price impact|  (%)")
    ax2.set_yscale("log")
    ax2.set_xlim(0, 10)
    ax2.legend(loc="lower right")
    save(fig, "fig_price_impact.pdf")


# --------------------------------------------------------------------------
# Fig 3 — Impermanent loss vs price ratio
# --------------------------------------------------------------------------
def fig_il_curves():
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    r = np.linspace(0.25, 4.0, 400)

    ax.plot(r, il_constant_product(r) * 100, color=C_CP, lw=2.1,
            label="Constant-product 50/50 (Uniswap V2)")
    ax.plot(r, il_weighted(r, 0.8) * 100, color=C_WP, lw=2.0, ls="-.",
            label="Weighted 80/20 (Balancer)")
    ax.plot(r, il_weighted(r, 0.98) * 100, color=C_WP, lw=1.6, ls=":",
            label="Weighted 98/2 (Balancer)")
    ax.plot(r, il_v3_range(r, 0.5, 2.0) * 100, color=C_V3, lw=2.0, ls="--",
            label="Uniswap V3 range $[0.5,\\,2.0]\\times$")

    # markers for canonical CP IL values
    for rr in [1.25, 1.5, 2.0, 4.0]:
        ax.scatter([rr], [il_constant_product(rr) * 100], color=C_CP, s=18, zorder=5)

    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("Price ratio  $r = P'/P$")
    ax.set_ylabel("Impermanent loss  (%)")
    ax.set_title("Impermanent loss vs price divergence")
    ax.set_ylim(-30, 2)
    ax.legend(loc="lower center")
    # annotate the classic CP numbers
    ax.annotate("-5.7% @ 2$\\times$", (2.0, il_constant_product(2.0) * 100),
                textcoords="offset points", xytext=(6, -2), fontsize=8.5, color=C_CP)
    ax.annotate("-20% @ 4$\\times$", (4.0, il_constant_product(4.0) * 100),
                textcoords="offset points", xytext=(-70, 2), fontsize=8.5, color=C_CP)
    save(fig, "fig_il_curves.pdf")


# --------------------------------------------------------------------------
# Fig 4 — Uniswap V3 capital efficiency and IL amplification
# --------------------------------------------------------------------------
def fig_v3_efficiency():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3))

    # capital efficiency vs (symmetric) range width
    widths = np.linspace(0.01, 0.9, 200)       # range = [1-w, 1+w] around price 1
    eff = [v3_capital_efficiency(1 - w, 1 + w) for w in widths]
    ax1.plot(np.array(widths) * 100, eff, color=C_V3, lw=2.1)
    for w in [0.1, 0.25, 0.5]:
        e = v3_capital_efficiency(1 - w, 1 + w)
        ax1.scatter([w * 100], [e], color=C_V3, s=22, zorder=5)
        ax1.annotate(f"±{int(w*100)}% → {e:.1f}×", (w * 100, e),
                     textcoords="offset points", xytext=(6, 4), fontsize=8.5)
    ax1.set_title("Uniswap V3 capital efficiency vs range width")
    ax1.set_xlabel("Half-range width around the price (%)")
    ax1.set_ylabel("Capital-efficiency multiplier vs V2")
    ax1.set_yscale("log")

    # IL amplification: V3 range vs V2 full range
    r = np.linspace(0.5, 2.0, 300)
    ax2.plot(r, il_constant_product(r) * 100, color=C_CP, lw=2.0, label="V2 full range")
    ax2.plot(r, il_v3_range(r, 0.8, 1.25) * 100, color=C_V3, lw=2.0, ls="--",
             label="V3 range $[0.8,\\,1.25]$")
    ax2.plot(r, il_v3_range(r, 0.5, 2.0) * 100, color=C_V3, lw=1.6, ls=":",
             label="V3 range $[0.5,\\,2.0]$")
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_title("Concentrated liquidity amplifies impermanent loss")
    ax2.set_xlabel("Price ratio  $r = P'/P$")
    ax2.set_ylabel("Impermanent loss  (%)")
    ax2.legend(loc="lower center")
    save(fig, "fig_v3_efficiency.pdf")


# --------------------------------------------------------------------------
# Fig 5 — StableSwap amplification A: curve flatness & local slippage
# --------------------------------------------------------------------------
def fig_stableswap_A():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3))
    X = 1_000_000.0

    # marginal price as the pool gets imbalanced, for several A
    imbalance = np.linspace(0.02, 0.95, 60)    # fraction of X drained
    for A, alpha in [(1, 0.4), (10, 0.6), (100, 0.85), (2000, 1.0)]:
        prices = []
        for frac in imbalance:
            ss = StableSwap(X * (1 - frac), X * (1 + frac), A=A)
            prices.append(ss.spot_price())
        ax1.plot(imbalance * 100, prices, color=C_SS, alpha=alpha, lw=1.9, label=f"$A={A}$")
    # constant product reference
    cp_prices = [ConstantProduct(X * (1 - f), X * (1 + f)).spot_price() for f in imbalance]
    ax1.plot(imbalance * 100, cp_prices, color=C_CP, lw=1.8, ls="--", label="Constant-product")
    ax1.set_title("StableSwap keeps price ≈ 1 until deeply imbalanced")
    ax1.set_xlabel("Pool imbalance (% of X removed)")
    ax1.set_ylabel("Marginal price of X (in Y)")
    ax1.set_ylim(0, 8)
    ax1.legend(loc="upper left")

    # price impact vs trade size for several A
    fracs = np.linspace(0.001, 0.5, 120)
    for A, alpha in [(1, 0.4), (10, 0.6), (100, 0.85), (2000, 1.0)]:
        ss = StableSwap(X, X, A=A, fee=0.0)
        imp = np.array([abs(ss.price_impact(f * X)) * 100 for f in fracs])
        ax2.plot(fracs * 100, imp, color=C_SS, alpha=alpha, lw=1.9, label=f"$A={A}$")
    cp = ConstantProduct(X, X, fee=0.0)
    imp = np.array([abs(cp.price_impact(f * X)) * 100 for f in fracs])
    ax2.plot(fracs * 100, imp, color=C_CP, lw=1.8, ls="--", label="Constant-product")
    ax2.set_title("Higher $A$ → lower slippage near the peg")
    ax2.set_xlabel("Trade size (% of X reserve)")
    ax2.set_ylabel("|Price impact|  (%)")
    ax2.set_ylim(0, 30)
    ax2.legend(loc="upper left")
    save(fig, "fig_stableswap_A.pdf")


# --------------------------------------------------------------------------
# Fig 6 — LP net PnL = fee income - IL  (break-even illustration)
# --------------------------------------------------------------------------
def fig_lp_pnl():
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    r = np.linspace(0.4, 2.5, 400)
    il = il_constant_product(r) * 100

    ax.plot(r, il, color=C_CP, lw=2.1, label="Impermanent loss (no fees)")
    for fee_income, c in [(1.0, "#9ecae1"), (3.0, "#4292c6"), (6.0, "#084594")]:
        ax.plot(r, il + fee_income, lw=1.8, color=c,
                label=f"Net PnL with +{fee_income:.0f}% fee income")
    ax.axhline(0, color="k", lw=0.8)
    ax.fill_between(r, 0, il, color=C_CP, alpha=0.08)
    ax.set_xlabel("Price ratio  $r = P'/P$")
    ax.set_ylabel("LP return vs HODL  (%)")
    ax.set_title("LP profitability: fees must outrun impermanent loss")
    ax.set_ylim(-15, 8)
    ax.legend(loc="lower center")
    save(fig, "fig_lp_pnl.pdf")


if __name__ == "__main__":
    fig_bonding_curves()
    fig_price_impact()
    fig_il_curves()
    fig_v3_efficiency()
    fig_stableswap_A()
    fig_lp_pnl()
    print("all analytic figures done")
