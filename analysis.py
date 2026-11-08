#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlankerPie · 数据分析脚本
==========================================================
读取课程服务器导出的 JSON / CSV，完成：
  1. 被试级描述统计（Flanker 四条件 RT、正确率；饼图 2D/3D 误差、正确率、RT）
  2. 推断统计（2×2 重复测量方差分析、配对 t 检验、单样本 t 检验）
  3. 出图（PNG）与 Markdown 报告

用法
----
  python analysis.py data/export_N2DRAL.json          # 分析真实数据
  python analysis.py data/export_N2DRAL.csv           # 也支持 CSV
  python analysis.py --demo 12                        # 用 12 人模拟数据跑通流程
  python analysis.py data/export.json -o results      # 指定输出目录

依赖：pandas / numpy / matplotlib（scipy 可选，缺失时只输出描述统计与 t 值）
  pip install -r requirements.txt

作者：FlankerPie 小组
"""

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖：pip install -r requirements.txt")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scipy import stats as sps

    HAS_SCIPY = True
except ImportError:  # pragma: no cover
    HAS_SCIPY = False

# ----------------------------------------------------------------- 常量
FLANKER_EXP = "flanker_distance"
PIE_EXP = "pie_3d_2d"
FLANKER_TIMEOUT = 1500
PIE_TOL = 5  # |误差| ≤ 5% 记作判断正确

COLORS = {"cong": "#C8A44A", "incong": "#0D2B5C", "2d": "#C8A44A", "3d": "#d64045"}
POS_ZH = {"front": "前景 front", "back": "后景 back", "left": "左侧 left", "right": "右侧 right"}


# ================================================================ 读数据
def load_records(path: Path):
    """读入导出文件，返回 records 列表：[{participant, experiment, trials, ...}]"""
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            recs = raw.get("records") or raw.get("data") or []
            print(f"项目：{raw.get('project', '?')} · {raw.get('title', '')}")
        else:
            recs = raw
        return [_normalize(r) for r in recs]

    if path.suffix.lower() in (".csv", ".tsv"):
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(path, sep=sep)
        df.columns = [c.strip().lower() for c in df.columns]
        pcol = _pick(df.columns, "participant", "subject", "pid", "被试")
        ecol = _pick(df.columns, "experiment", "exp", "task")
        if pcol is None or ecol is None:
            sys.exit("CSV 里找不到 participant / experiment 列，请改用 JSON 导出。")
        used = {pcol, ecol}
        out = []
        for (exp, pid), g in df.groupby([ecol, pcol], dropna=False):
            trials = []
            for _, row in g.iterrows():
                t = {k: row[k] for k in g.columns if k not in used}
                trials.append({k: (None if pd.isna(v) else v) for k, v in t.items()})
            out.append({"participant": str(pid), "experiment": str(exp), "trials": trials})
        return out

    sys.exit(f"不支持的文件类型：{path.suffix}（请用 .json 或 .csv）")


def _pick(cols, *names):
    for n in names:
        if n in cols:
            return n
    return None


def _normalize(rec: dict):
    """服务器的 trials 可能是字符串（JSON），统一成 list[dict]。"""
    trials = rec.get("trials")
    if isinstance(trials, str):
        try:
            trials = json.loads(trials)
        except json.JSONDecodeError:
            trials = []
    if not isinstance(trials, list):
        trials = []
    trials = [json.loads(t) if isinstance(t, str) else t for t in trials]
    rec["trials"] = [t for t in trials if isinstance(t, dict)]
    return rec


# ================================================================ Flanker
def flanker_frame(records):
    rows = []
    for rec in records:
        if rec.get("experiment") != FLANKER_EXP:
            continue
        pid = rec.get("participant", "?")
        for t in rec.get("trials", []):
            dist = t.get("dist")
            cong = t.get("cong")
            if dist is None and isinstance(t.get("cond"), str) and "_" in t["cond"]:
                dist = t["cond"].split("_")[0]
            if cong is None and isinstance(t.get("cond"), str) and "_" in t["cond"]:
                cong = 1 if t["cond"].endswith("cong") else 0
            if dist is None or cong is None:
                continue
            rt = t.get("rt")
            rows.append(
                {
                    "participant": pid,
                    "dist": str(dist),
                    "cong": int(cong),
                    "rt": float(rt) if rt not in (None, "") else np.nan,
                    "correct": int(t.get("correct") or 0),
                    "timeout": int(t.get("timeout") or 0),
                    "gap_actual": t.get("gap_actual"),
                    "aoi_target": t.get("aoi_target"),
                    "aoi_flank": t.get("aoi_flank"),
                    "aoi_off": t.get("aoi_off"),
                    "gaze_n": t.get("gaze_n"),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["rt"] = df["rt"].where((df["rt"] > 100) & (df["rt"] <= FLANKER_TIMEOUT + 50))
    return df


def flanker_stats(df):
    """返回（四条件均值表, 被试级宽表）"""
    ok = df[(df["correct"] == 1) & df["rt"].notna()].copy()
    ok["cell"] = ok["dist"] + "_" + np.where(ok["cong"] == 1, "cong", "incong")

    subj = ok.pivot_table(index="participant", columns="cell", values="rt", aggfunc="mean")
    for c in ["near_cong", "near_incong", "far_cong", "far_incong"]:
        if c not in subj:
            subj[c] = np.nan
    subj = subj[["near_cong", "near_incong", "far_cong", "far_incong"]].dropna()

    acc = df.groupby("participant")["correct"].mean()
    table = []
    for cell, label in [
        ("near_cong", "近 · 一致"),
        ("near_incong", "近 · 不一致"),
        ("far_cong", "远 · 一致"),
        ("far_incong", "远 · 不一致"),
    ]:
        sub = df[df["dist"] + "_" + np.where(df["cong"] == 1, "cong", "incong") == cell]
        vals = subj[cell].dropna()
        table.append(
            {
                "条件": label,
                "RT (ms)": vals.mean() if len(vals) else np.nan,
                "SE": vals.std(ddof=1) / math.sqrt(len(vals)) if len(vals) > 1 else np.nan,
                "正确率 (%)": sub["correct"].mean() * 100 if len(sub) else np.nan,
                "n 试次": len(sub),
            }
        )
    return pd.DataFrame(table), subj, acc


def rm_anova_2x2(long_df, dv="rt"):
    """2×2 被试内方差分析：long_df 需含 subj / A / B / dv，每格一个观测。"""
    piv = long_df.pivot_table(index="subj", columns=["A", "B"], values=dv).dropna()
    n = len(piv)
    if n < 2:
        return None
    cells = piv.values  # n × 4
    ncell = cells.shape[1]
    grand = cells.mean()
    # 用 pivot 的列层级还原因素均值
    col_a = piv.columns.get_level_values(0)
    col_b = piv.columns.get_level_values(1)
    a_levels = list(dict.fromkeys(col_a))
    b_levels = list(dict.fromkeys(col_b))
    mean_cell = {c: cells[:, i].mean() for i, c in enumerate(piv.columns)}
    mean_a = {a: np.mean([mean_cell[(a, b)] for b in b_levels]) for a in a_levels}
    mean_b = {b: np.mean([mean_cell[(a, b)] for a in a_levels]) for b in b_levels}
    subj_mean = cells.mean(axis=1)

    ss_a = n * len(b_levels) * sum((mean_a[a] - grand) ** 2 for a in a_levels)
    ss_b = n * len(a_levels) * sum((mean_b[b] - grand) ** 2 for b in b_levels)
    ss_ab = n * sum(
        (mean_cell[(a, b)] - mean_a[a] - mean_b[b] + grand) ** 2 for a in a_levels for b in b_levels
    )
    ss_subj = ncell * float(((subj_mean - grand) ** 2).sum())
    ss_total = float(((cells - grand) ** 2).sum())
    ss_err = ss_total - ss_a - ss_b - ss_ab - ss_subj
    df_err = (n - 1) * (ncell - 1)
    ms_err = ss_err / df_err if df_err > 0 else np.nan

    def F(ss, dfn=1):
        return (ss / dfn) / ms_err if ms_err and ms_err > 0 else np.nan

    def p(f, dfn=1):
        if not HAS_SCIPY or not np.isfinite(f):
            return np.nan
        return float(sps.f.sf(f, dfn, df_err))

    # long_df 中 A = dist（近/远）、B = cong（一致/不一致）
    rows = [
        ("目标—干扰距离 (dist)", ss_a, F(ss_a), p(F(ss_a))),
        ("Flanker 一致性 (cong)", ss_b, F(ss_b), p(F(ss_b))),
        ("一致性 × 距离", ss_ab, F(ss_ab), p(F(ss_ab))),
    ]
    return pd.DataFrame(
        [{"效应": r[0], "F(1,%d)" % df_err: r[2], "p": r[3], "η²p": r[1] / (r[1] + ss_err)} for r in rows]
    )


# ================================================================ 饼图
def pie_frame(records):
    rows = []
    for rec in records:
        if rec.get("experiment") != PIE_EXP:
            continue
        pid = rec.get("participant", "?")
        for t in rec.get("trials", []):
            true_pct = t.get("true_pct")
            resp = t.get("resp_pct")
            if true_pct is None:
                continue
            view = t.get("view") or t.get("cond")
            err = t.get("signed_err")
            if err is None and resp not in (None, ""):
                err = float(resp) - float(true_pct)
            rows.append(
                {
                    "participant": pid,
                    "view": str(view),
                    "pos": t.get("pos") or "?",
                    "true_pct": float(true_pct),
                    "resp_pct": float(resp) if resp not in (None, "") else np.nan,
                    "signed_err": float(err) if err not in (None, "") else np.nan,
                    "abs_err": abs(float(err)) if err not in (None, "") else np.nan,
                    "correct": int(t.get("correct") or 0),
                    "rt": float(t["rt"]) if t.get("rt") not in (None, "") else np.nan,
                    "aoi_sector": t.get("aoi_sector"),
                    "aoi_chart": t.get("aoi_chart"),
                    "aoi_resp": t.get("aoi_resp"),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["abs_err"] = df["signed_err"].abs()
    return df


def pie_stats(df):
    subj = df.pivot_table(index="participant", columns="view", values="abs_err", aggfunc="mean").dropna()
    table = []
    for view, label in [("2d", "2D 平面饼图"), ("3d", "3D 透视饼图")]:
        sub = df[df["view"] == view]
        table.append(
            {
                "条件": label,
                "平均绝对误差 (%)": sub["abs_err"].mean(),
                "SE": sub["abs_err"].std(ddof=1) / math.sqrt(sub["abs_err"].notna().sum())
                if sub["abs_err"].notna().sum() > 1
                else np.nan,
                "有符号误差 (%)": sub["signed_err"].mean(),
                "正确率 (%)": sub["correct"].mean() * 100 if len(sub) else np.nan,
                "反应时 (ms)": sub["rt"].mean(),
                "n 试次": len(sub),
            }
        )
    return pd.DataFrame(table), subj


def paired_t(a, b):
    """配对 t 检验；返回 (t, p, df, 均值差)"""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    a, b = a[mask], b[mask]
    if len(a) < 2:
        return np.nan, np.nan, 0, np.nan
    if HAS_SCIPY:
        r = sps.ttest_rel(a, b)
        return float(r.statistic), float(r.pvalue), len(a) - 1, float(a.mean() - b.mean())
    d = a - b
    t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    return float(t), np.nan, len(d) - 1, float(d.mean())


def one_sample_t(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.nan, np.nan
    if HAS_SCIPY:
        r = sps.ttest_1samp(x, 0)
        return float(r.statistic), float(r.pvalue)
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))), np.nan


# ================================================================ 作图
def _bar(ax, labels, values, errs, colors, ylabel, title):
    x = np.arange(len(labels))
    bars = ax.bar(x, values, yerr=errs, capsize=5, color=colors, width=0.58,
                  error_kw={"elinewidth": 1.2, "ecolor": "#33415c"})
    for b, v, e in zip(bars, values, errs):
        if np.isfinite(v):
            top = v + (e if np.isfinite(e) else 0)
            ax.text(b.get_x() + b.get_width() / 2, top + (max(values) * 0.02), f"{v:.0f}",
                    ha="center", va="bottom", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle=":")


def plot_flanker(df, out: Path):
    ok = df[(df["correct"] == 1) & df["rt"].notna()]
    if ok.empty:
        return None
    ok = ok.copy()
    ok["cell"] = ok["dist"] + "_" + np.where(ok["cong"] == 1, "cong", "incong")
    order = ["near_cong", "near_incong", "far_cong", "far_incong"]
    labels = ["Near·Cong", "Near·Incong", "Far·Cong", "Far·Incong"]
    per_subj = ok.pivot_table(index="participant", columns="cell", values="rt", aggfunc="mean")
    means, errs = [], []
    for c in order:
        v = per_subj[c].dropna() if c in per_subj else pd.Series(dtype=float)
        means.append(v.mean())
        errs.append(v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else 0)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    _bar(axes[0], labels, means, errs, [COLORS["cong"], COLORS["incong"], COLORS["cong"], COLORS["incong"]],
         "RT (ms)", "Flanker RT by condition")

    # 干扰效应（不一致 − 一致），按距离
    eff_near = per_subj.get("near_incong", pd.Series(dtype=float)) - per_subj.get("near_cong", pd.Series(dtype=float))
    eff_far = per_subj.get("far_incong", pd.Series(dtype=float)) - per_subj.get("far_cong", pd.Series(dtype=float))
    eff_near, eff_far = eff_near.dropna(), eff_far.dropna()
    e_means = [eff_near.mean(), eff_far.mean()]
    e_errs = [
        eff_near.std(ddof=1) / math.sqrt(len(eff_near)) if len(eff_near) > 1 else 0,
        eff_far.std(ddof=1) / math.sqrt(len(eff_far)) if len(eff_far) > 1 else 0,
    ]
    ax = axes[1]
    bars = ax.bar([0, 1], e_means, yerr=e_errs, capsize=5, width=0.5,
                  color=["#8c6d1f", "#5b7fb5"], error_kw={"elinewidth": 1.2, "ecolor": "#33415c"})
    ax.axhline(0, color="#33415c", lw=1, ls="--")
    for b, v in zip(bars, e_means):
        if np.isfinite(v):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:+.0f}", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=10)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Near (gap 2 px)", "Far (gap 120 px)"], fontsize=10)
    ax.set_ylabel("Flanker effect (ms)", fontsize=11)
    ax.set_title("Interference cost: Incongruent − Congruent", fontsize=13, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle=":")

    fig.tight_layout()
    p = out / "fig1_flanker_rt.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    return p


def plot_pie(df, out: Path):
    if df.empty:
        return []
    paths = []
    # 1) 平均绝对误差
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    vals, errs = [], []
    for view in ["2d", "3d"]:
        per = df[df["view"] == view].groupby("participant")["abs_err"].mean().dropna()
        vals.append(per.mean())
        errs.append(per.std(ddof=1) / math.sqrt(len(per)) if len(per) > 1 else 0)
    _bar(axes[0], ["2D pie", "3D pie"], vals, errs, [COLORS["2d"], COLORS["3d"]],
         "Mean |error| (%)", "Proportion judgment error")

    # 2) 有符号误差 × 扇区方位
    ax = axes[1]
    positions = [p for p in ["front", "back", "left", "right"] if p in set(df["pos"])]
    x = np.arange(len(positions))
    w = 0.36
    for i, view in enumerate(["2d", "3d"]):
        means, errs2 = [], []
        for pos in positions:
            per = df[(df["view"] == view) & (df["pos"] == pos)].groupby("participant")["signed_err"].mean().dropna()
            means.append(per.mean() if len(per) else np.nan)
            errs2.append(per.std(ddof=1) / math.sqrt(len(per)) if len(per) > 1 else 0)
        ax.bar(x + (i - 0.5) * w, means, w, yerr=errs2, capsize=4, label=view.upper(),
               color=COLORS[view], error_kw={"elinewidth": 1.1, "ecolor": "#33415c"})
    ax.axhline(0, color="#33415c", lw=1.2, ls="--")
    ax.set_xticks(x)
    ax.set_xticklabels(positions, fontsize=10)
    ax.set_ylabel("Signed error (%)  >0 overestimate", fontsize=10.5)
    ax.set_title("Signed error by sector position", fontsize=13, fontweight="bold")
    ax.legend(frameon=False, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle=":")
    fig.tight_layout()
    p = out / "fig2_pie_error.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    paths.append(p)

    # 3) AOI 停留时间（有则画）
    if df["aoi_sector"].notna().any():
        fig, ax = plt.subplots(figsize=(6.4, 4))
        cats = ["aoi_sector", "aoi_chart", "aoi_resp"]
        labels = ["Sector", "Rest of pie", "Response UI"]
        x = np.arange(len(cats))
        w = 0.36
        for i, view in enumerate(["2d", "3d"]):
            means = [df[df["view"] == view][c].mean() for c in cats]
            ax.bar(x + (i - 0.5) * w, means, w, label=view.upper(), color=COLORS[view])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylabel("Mean dwell time per trial (ms)", fontsize=10.5)
        ax.set_title("AOI dwell time", fontsize=13, fontweight="bold")
        ax.legend(frameon=False, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        p = out / "fig3_pie_aoi.png"
        fig.savefig(p, dpi=160)
        plt.close(fig)
        paths.append(p)
    return paths


# ================================================================ 报告
def md_table(df, floatfmt="{:.1f}"):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (int, np.integer)):
                cells.append(str(int(v)))
            elif isinstance(v, float) or isinstance(v, np.floating):
                cells.append("—" if not np.isfinite(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def p_txt(p):
    if not np.isfinite(p):
        return "p = —"
    if p < 0.001:
        return "p < .001"
    return f"p = {p:.3f}"


def analyze(records, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    md = ["# FlankerPie 数据分析报告", ""]

    fdf = flanker_frame(records)
    pdf = pie_frame(records)
    md.append(f"数据：{len(records)} 条提交记录 ｜ Flanker 试次 {len(fdf)} ｜ 饼图试次 {len(pdf)}")
    md.append("")

    # ---------- Flanker ----------
    if not fdf.empty:
        table, subj, acc = flanker_stats(fdf)
        n_fl = fdf["participant"].nunique()
        md += ["## 实验一 · Flanker 距离", "", f"被试数 n = **{n_fl}**", "", "### 描述统计", "",
               md_table(table), ""]

        # 2×2 被试内 ANOVA
        long = []
        for pid, row in subj.iterrows():
            for cell, val in row.items():
                dist, cong = cell.split("_")
                long.append({"subj": pid, "A": dist, "B": "cong" if cong == "cong" else "incong", "rt": val})
        anova = rm_anova_2x2(pd.DataFrame(long))
        if anova is not None:
            md += ["### 2×2 重复测量方差分析（因变量：正确试次 RT）", "", md_table(anova, "{:.3f}"), ""]
            try:
                row = anova.iloc[2]
                pv = row["p"]
                if np.isfinite(pv):
                    md.append(
                        "交互作用" + ("显著" if pv < 0.05 else "不显著") + f"（{p_txt(pv)}）："
                        + ("距离确实调节了 Flanker 效应的大小。" if pv < 0.05
                           else "尚无证据表明距离调节了 Flanker 效应，可能与试次量或被试数有关。")
                    )
            except Exception:
                pass
            md.append("")

        # 干扰效应与配对检验
        eff = subj["near_incong"] - subj["near_cong"]
        efff = subj["far_incong"] - subj["far_cong"]
        t, p, dfree, dm = paired_t(eff, efff)
        md += ["### 干扰效应（不一致 − 一致）", "",
               f"- 近距：{eff.mean():+.1f} ms（SE = {eff.std(ddof=1)/math.sqrt(len(eff)):.1f}）",
               f"- 远距：{efff.mean():+.1f} ms（SE = {efff.std(ddof=1)/math.sqrt(len(efff)):.1f}）",
               f"- 近 vs 远 配对 t 检验：t({dfree}) = {t:.2f}，{p_txt(p)}，差值 {dm:+.1f} ms", ""]
        acc_all = fdf["correct"].mean() * 100
        md += [f"总体正确率 {acc_all:.1f}%，超时 {int(fdf['timeout'].sum())} 次。", ""]

        fig = plot_flanker(fdf, out_dir)
        if fig:
            md += [f"![flanker]({fig.name})", ""]

        # AOI
        with_gaze = fdf[fdf["gaze_n"].fillna(0) > 0]
        if not with_gaze.empty:
            md += ["### 兴趣区（AOI）停留时间", "",
                   f"- 目标字母区：{with_gaze['aoi_target'].mean():.0f} ms/试次",
                   f"- 两侧干扰区：{with_gaze['aoi_flank'].mean():.0f} ms/试次",
                   f"- 其他区域：{with_gaze['aoi_off'].mean():.0f} ms/试次", ""]
    else:
        md += ["## 实验一 · Flanker 距离", "", "_没有找到该实验的数据。_", ""]

    # ---------- 饼图 ----------
    if not pdf.empty:
        table, subj2 = pie_stats(pdf)
        n_pie = pdf["participant"].nunique()
        md += ["## 实验二 · 3D 透视饼图 vs 2D 平面饼图", "", f"被试数 n = **{n_pie}**", "",
               "### 描述统计", "", md_table(table), ""]

        if "2d" in subj2 and "3d" in subj2:
            t, p, dfree, dm = paired_t(subj2["3d"], subj2["2d"])
            md += ["### 2D vs 3D 配对 t 检验（平均绝对误差）", "",
                   f"t({dfree}) = {t:.2f}，{p_txt(p)}，3D − 2D = {dm:+.2f} 个百分点", ""]
            if np.isfinite(p):
                if dm > 0 and p < 0.05:
                    md.append("**结果支持预测：3D 透视饼图的判断误差显著大于 2D 平面饼图。**")
                elif p < 0.05:
                    md.append("**结果与预测相反：3D 的误差显著小于 2D。**")
                else:
                    md.append("两种呈现方式的误差差异未达显著，可能与试次量或被试数有关。")
                md.append("")

        # 前后景不对称
        md += ["### 3D 中前景 / 后景的偏差（预测：前景高估、后景低估）", ""]
        for pos in ["front", "back", "left", "right"]:
            per = pdf[(pdf["view"] == "3d") & (pdf["pos"] == pos)].groupby("participant")["signed_err"].mean()
            if len(per) == 0:
                continue
            t1, p1 = one_sample_t(per.values)
            md.append(f"- {POS_ZH.get(pos, pos)}：{per.mean():+.2f}%，单样本 t({len(per)-1}) = {t1:.2f}，{p_txt(p1)}")
        md.append("")
        figs = plot_pie(pdf, out_dir)
        for f in figs:
            md += [f"![pie]({f.name})", ""]
    else:
        md += ["## 实验二 · 3D / 2D 饼图比例判断", "", "_没有找到该实验的数据。_", ""]

    md += [
        "---",
        "",
        "> 图表使用英文标签以避免字体缺失；统计使用被试级均值（先算每名被试，再算组均值）。",
        "> 若只看到描述统计而没有 p 值，说明环境中缺少 scipy：`pip install scipy`。",
        "",
    ]

    report = out_dir / "report.md"
    report.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\n报告已写入：{report}")
    return report


# ================================================================ 模拟数据
def demo_records(n_subj=12, seed=7):
    rng = np.random.default_rng(seed)
    recs = []
    for s in range(n_subj):
        pid = f"P{s + 1:02d}"
        base = rng.normal(470, 60)
        ftrials = []
        for dist in ["near", "far"]:
            for cong in [1, 0]:
                for k in range(20):
                    cost = 0 if cong else (62 if dist == "near" else 34)
                    rt = base + cost + rng.normal(0, 70)
                    ftrials.append(
                        {
                            "cond": f"{dist}_{'cong' if cong else 'incong'}",
                            "dist": dist,
                            "cong": cong,
                            "rt": int(max(180, min(1490, rt))),
                            "correct": int(rng.random() > 0.06),
                            "timeout": 0,
                            "gap_actual": 2.0 if dist == "near" else 120.0,
                            "aoi_target": int(rng.normal(620, 120)),
                            "aoi_flank": int(rng.normal(140, 60)),
                            "aoi_off": int(rng.normal(180, 60)),
                            "gaze_n": 22,
                        }
                    )
        ptrials = []
        for view in ["2d", "3d"]:
            for value in [15, 22, 30, 38, 45]:
                for pos in ["front", "back", "left", "right"]:
                    bias = 0.4 if view == "2d" else {"front": 4.6, "back": -4.2, "left": 1.2, "right": 0.8}[pos]
                    err = bias + rng.normal(0, 4.5)
                    resp = int(max(1, min(99, round(value + err))))
                    err2 = resp - value
                    ptrials.append(
                        {
                            "cond": view,
                            "view": view,
                            "pos": pos,
                            "pos_deg": {"front": 90, "back": 270, "left": 180, "right": 0}[pos],
                            "true_pct": value,
                            "resp_pct": resp,
                            "signed_err": err2,
                            "abs_err": abs(err2),
                            "correct": int(abs(err2) <= PIE_TOL),
                            "rt": int(rng.normal(2400, 700)),
                            "aoi_sector": int(rng.normal(900, 200)),
                            "aoi_chart": int(rng.normal(500, 150)),
                            "aoi_resp": int(rng.normal(600, 180)),
                        }
                    )
        recs.append({"participant": pid, "experiment": FLANKER_EXP, "trials": ftrials})
        recs.append({"participant": pid, "experiment": PIE_EXP, "trials": ptrials})
    return recs


# ================================================================ main
def main():
    ap = argparse.ArgumentParser(description="FlankerPie 数据分析")
    ap.add_argument("input", nargs="?", help="导出的 .json 或 .csv")
    ap.add_argument("-o", "--out", default="results", help="输出目录（默认 results/）")
    ap.add_argument("--demo", type=int, metavar="N", help="用 N 名被试的模拟数据跑通流程")
    args = ap.parse_args()

    if args.demo:
        records = demo_records(args.demo)
        print(f"[demo] 生成 {args.demo} 名被试的模拟数据")
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            sys.exit(f"找不到文件：{path}")
        records = load_records(path)
    else:
        ap.print_help()
        sys.exit("\n请给出输入文件，或用 --demo 生成模拟数据。")

    if not records:
        sys.exit("文件里没有记录：先去 /hw2/admin 看收数进度，或让被试做完后再导出。")

    analyze(records, Path(args.out))
    if not HAS_SCIPY:
        print("\n提示：未安装 scipy，p 值不可用（pip install scipy）")


if __name__ == "__main__":
    main()
