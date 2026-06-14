# CLAUDE.md — 專案執行記錄

## 專案目標
依 `BitDA_final.pdf` 題目，自選一題完成 BitDA 期末專題報告（只需 PDF）。
**選題：題目 A — 各種 AMM 機制比較研究**（Constant-Product / Stable-Swap / Weighted-Pool）。
理由：此題同時要求數學模型、情境模擬、與滑點/LP收益/無常損失視覺化，可實際跑模擬產生數據與圖表，兼顧「報告品質」與「額外內容」評分。
報告語言：繁體中文 ＋ 英文術語（經使用者確認）。

## 本次執行做了什麼（2026-06-14）
1. **讀題**：解析 10 個題目（A–J），選定題目 A。
2. **環境**：確認 XeLaTeX (TeX Live 2025) + PingFang TC 中文字型；建立 `.venv` 安裝 matplotlib/numpy/scipy。
3. **Survey（workflow）**：用多代理 workflow（13 agents、486K tokens）平行研究四種 AMM + 滑點 + IL/LVR + 近期發展，
   並對抗式驗證所有公式（**修正 2 處**：V3 tick 公式對數底、Curve V2 repegging 多餘的 1/2 係數），
   另由專責 agent 蒐集並驗證 38 筆參考文獻（題目原本只給 3 個 whitepaper）。輸出 `report/refs.bib`、`sim/survey_digest.txt`。
4. **模擬程式**（`sim/`）：
   - `amm.py`：三種 AMM 池參考實作（StableSwap 以 scipy.brentq 解不變量）＋ IL/資本效率閉式解。
   - `make_figures.py`：6 張解析圖（鍵結曲線、價格衝擊、無常損失、V3 資本效率、StableSwap A、LP 損益）。
   - `simulate_lp.py`：蒙地卡羅（5000 路徑 × 9 情境）→ 報酬分佈圖、情境圖、`report/tab_mc.tex`。
5. **報告**（`report/main.tex`）：11 節 + 附錄，15 頁；含 8 張圖、4 張表、1 張 TikZ 設計空間圖、28 筆引用（numeric 格式）。
   XeLaTeX + xeCJK 編譯，三遍 + bibtex，無錯誤、無 undefined 引用。
6. **交付**：根目錄 `AMM機制比較研究_BitDA期末專題.pdf`（= `report/main.pdf`）。
7. **收尾**：建立 `.gitignore`（排除 217MB 的 `.venv` 與 LaTeX 中間檔）、`README.md`。

## 第二次執行：完整 QA 審查（2026-06-14）
用 30-agent review workflow（math/code/consistency/citations/quality/build 六面向，每個發現皆對抗式驗證）全面複查，確認 17 個問題、去重為 5 類，全部修正：
1. **(critical) Table 2 無常損失表 Balancer 兩列數值手key錯誤**（80/20、95/5 的中間欄位與 `il_weighted` 不符）→ 改為**程式自動產生**（新增 `sim/make_il_table.py` → `report/tab_il.tex`，main.tex 改 `\input`），杜絕再次漂移。
2. **(major) 高權重池命名不一致**（表/內文 95/5 vs 摘要/圖/MC/模擬 98/2）→ 全文統一成 **98/2**（圖與模擬本就用 98/2）；§5 保留 95/5 作為 Martinelli 發表值的佐證。
3. **(major) `amm.py` il_v3_range docstring「IL saturates」錯誤**（程式正確地發散趨向 −100%）→ 改寫 docstring（無程式邏輯變動）。
4. **(minor) 10 筆已驗證但未引用的文獻**會被 plainnat 丟棄 → 在 §3.2/§4/§5/§7/§10 自然處補引用，參考清單由 28 → **38 筆**全數呈現。
5. **(nit) 潤飾**：表頭「動者」→「變動資產」；TikZ 設計空間圖以 `\resizebox` 包裹消除 107pt overfull；docstring「Approximate」措辭。
複查結論：**底層數學、模擬、圖表全部正確，原錯誤皆為轉錄/文件層級**。修正後重編譯 0 錯誤、0 undefined、38 筆引用、15 頁。

## 已知小瑕疵 / 注意事項
- 作者欄已填：廖振翔／B11705058。
- 編譯剩 2 處 overfull hbox（40pt、16pt，皆 CJK 段落，無可見溢出）；TikZ 的 107pt 已用 `\resizebox` 修掉。
- IL 表（tab_il.tex）與 MC 表（tab_mc.tex）皆由 `sim/` 程式自動產生，勿手改。
- `refs.bib` 為已編輯之最終檔；若由 workflow 輸出重新產生，需重套作者欄逗號→`and` 與特殊字元跳脫修正。
- 真實 TVL/成交量為 ~2025–2026 概略快照，數值會波動（報告中已註明）。
- 已發佈為 public GitHub repo：https://github.com/ZhenXiang6/amm-mechanisms-comparison

## 接下來的 TODO（可選的加分項，使用者未要求）
- [ ] （加分項）錄製 demo 影片並上傳 YouTube。
- [ ] （加分項）製作簡報（簡明扼要）。
- [ ] （可選）若要進一步強化：把蒙地卡羅改成完整 agent-based 套利模擬（逐步 root-find 各池價格），目前用閉式 PV(r) 近似（已於報告說明假設）。
