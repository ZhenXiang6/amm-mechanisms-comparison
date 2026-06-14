# BitDA 期末專題 — 題目 A：各種 AMM 機制比較研究

比較三大自動造市商（AMM）家族 —— **Constant-Product**（Uniswap V2/V3）、**Stable-Swap**（Curve）與
**Weighted-Pool**（Balancer）—— 在數學模型、滑點、無常損失與 LP 收益上的差異，並以蒙地卡羅模擬量化不同波動率與交易量情境下的 LP 報酬。

> **最終交付物**：[`AMM機制比較研究_BitDA期末專題.pdf`](AMM機制比較研究_BitDA期末專題.pdf)（即 `report/main.pdf`，共 15 頁，繁體中文＋英文術語）。

---

## 報告涵蓋內容（對應題目三項要求）

| 題目要求 | 對應章節 |
|---|---|
| (1) 分析三種 AMM 的數學模型與核心機制 | §2 CFMM 統一框架、§3 Uniswap V2/V3、§4 Curve、§5 Balancer |
| (2) 模擬不同流動性與交易量情境 | §8 蒙地卡羅模擬（5000 條路徑 × 9 種波動率/成交量情境） |
| (3) 視覺化滑點、LP 收益與無常損失差異 | §6 滑點、§7 無常損失與 LVR（共 8 張 Python 計算之圖表） |

**額外內容**：CFMM 統一框架、統一深度-滑點定律 `slippage ≈ Δx/(2·D)`、Loss-Versus-Rebalancing（LVR）理論、
綜合比較矩陣、AMM 設計空間定位圖、Uniswap v4 hooks、LVR/MEV 緩解型 AMM（FM-AMM、CoW AMM、am-AMM）、JIT 流動性、真實市場規模。
全文 28 筆參考文獻皆對照一手白皮書與學術論文，並經多代理對抗式驗證。

---

## 專案結構

```
bitDA-FP/
├── AMM機制比較研究_BitDA期末專題.pdf   # 最終報告（交付物）
├── BitDA_final.pdf                      # 原始題目
├── report/
│   ├── main.tex                         # 報告 LaTeX 原始檔（XeLaTeX）
│   ├── refs.bib                         # 參考文獻（38 筆，URL 皆驗證可達）
│   ├── tab_mc.tex                       # 蒙地卡羅結果表（由模擬產生）
│   ├── tab_il.tex                       # 無常損失表（由 make_il_table.py 產生）
│   ├── main.pdf                         # 編譯輸出
│   └── figures/                         # 8 張向量圖（PDF）
└── sim/
    ├── amm.py                           # 三種 AMM 池的參考實作
    ├── make_figures.py                  # 產生 6 張解析圖
    ├── make_il_table.py                 # 產生無常損失表 tab_il.tex
    ├── simulate_lp.py                   # 蒙地卡羅模擬 + 2 張圖 + 結果表
    └── survey_digest.txt                # survey 研究摘要（寫作參考）
```

---

## 重現方式

### 1. 環境（Python 圖表與模擬）

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install matplotlib numpy scipy
```

### 2. 產生所有圖表與模擬數據

```bash
cd sim
../.venv/bin/python make_figures.py     # 6 張解析圖 → report/figures/
../.venv/bin/python simulate_lp.py      # 蒙地卡羅 → 2 張圖 + report/tab_mc.tex
../.venv/bin/python make_il_table.py    # 無常損失表 → report/tab_il.tex
```

### 3. 編譯報告（需 XeLaTeX + 中文字型，例：macOS 內建 PingFang TC）

```bash
cd report
xelatex -interaction=nonstopmode main.tex
bibtex   main
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

---

## 核心結論

1. 三者本質皆為 **CFMM**，差別只在交易函數 φ：Uniswap 用 `xy=k`、Balancer 用加權幾何平均、Curve 用以放大係數 *A* 調控的「和–積」混合。
2. **滑點服從單一規則** `slippage ≈ Δx/(2·D)`；局部深度 *D* 可被 Curve 的 *A*、V3 的集中度 *L*、或 Balancer 的權重放大。
3. **無常損失是價格比的函數**；Balancer 加權可降低之、Curve 對 pegged 資產近乎為零、V3 集中流動性以放大無常損失換取資本效率。
4. **LVR** 提供比傳統無常損失更貼近真實的造市成本視角，並驅動了 v4 動態費率與批次/拍賣型 AMM 等前沿設計。
5. 模擬證實：**手續費（由成交量驅動）必須跑贏無常損失（由波動率驅動）**，故「最佳 AMM」取決於資產特性與 LP 目標。
