"""
make_il_table.py — emit report/tab_il.tex programmatically from amm.py so the
impermanent-loss table can never drift from the formulas/code.
Pools: constant-product 50/50, Balancer 80/20 and 98/2 (weight on the moving
asset).  98/2 matches the pool used in the figures and the Monte-Carlo section.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from amm import il_constant_product, il_weighted

RS = [1.25, 1.5, 2, 3, 4, 5]
OUT = os.path.join(os.path.dirname(__file__), "..", "report", "tab_il.tex")


def cells(fn):
    return " & ".join(f"${fn(r) * 100:.2f}$" for r in RS)


def main():
    rows = [
        ("Constant-product 50/50", lambda r: il_constant_product(r)),
        (r"Balancer 80/20（變動資產 $w{=}0.8$）", lambda r: il_weighted(r, 0.8)),
        (r"Balancer 98/2（變動資產 $w{=}0.98$）", lambda r: il_weighted(r, 0.98)),
    ]
    lines = [
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"價格比 $r=P'/P$ & 1.25 & 1.5 & 2 & 3 & 4 & 5 \\",
        r"\midrule",
    ]
    for label, fn in rows:
        lines.append(f"{label} & {cells(fn)} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
