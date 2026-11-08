# 🥧 FlankerPie · 注意实验平台

**🔗 在线实验：** https://你的用户名(https://huaci52777.github.io/FlankerPie/)/ ←（部署后把这一行换成真实链接）

> 工程心理学作业二 ——「构建一个『注意实验』：重现 + 改进」
> 纯 HTML/CSS/原生 JavaScript 单文件实验程序 + Python 数据分析，零框架、零构建。

[![Experiments](https://img.shields.io/badge/experiments-2-C8A44A)]()
[![Trials](https://img.shields.io/badge/Flanker-80%20trials-0D2B5C)]()
[![Trials](https://img.shields.io/badge/Pie-40%20trials-d64045)]()
[![Tracking](https://img.shields.io/badge/gaze-WebGazer.js%20%2B%20mouse-5b7fb5)]()

---

## 这是什么

一个可以直接在浏览器里打开就做的注意实验平台，包含两个经典范式的「重现 + 改进」：

| 实验 | 范式 | 改进操控 | 设计 | 试次 |
|---|---|---|---|---|
| 一 | **Eriksen Flanker**（1974） | 目标—干扰**空间距离**：紧贴 2 px vs 拉开 120 px | 2（一致性）× 2（距离）被试内 | 练习 8 + 正式 80 |
| 二 | **Cleveland & McGill (1984) 图形比例判断** | **3D 透视饼图 vs 2D 平面饼图**（透视错觉：前景高估、后景低估） | 5 占比 × 4 方位，2D/3D 完全配对 | 练习 4 + 正式 40 |

同步记录 **行为数据**（RT、正确率、超时、滑块作答）与 **眼动/鼠标追踪数据**（WebGazer.js 摄像头眼动 + One-Euro 滤波 + 9 点校准；可降级为鼠标模式），并按兴趣区（AOI：目标字母区 / 干扰区 / 红色扇区 / 作答区）统计注视停留时间。

## 怎么做实验

1. **在线直接做**（推荐，需摄像头眼动时选这种）：
(https://huaci52777.github.io/FlankerPie/) —— 打开后填昵称编号 → 选「启用摄像头眼动」或「仅鼠标」→ 校准 → 依次完成两个实验。
2. **本地运行**：
   ```bash
   python serve.py        # 或任何静态服务器
   # 打开 http://127.0.0.1:8765/
   ```
3. 数据会实时上传到课程服务器（`POST /api/hw2/submit`，项目码 `N2DRAL`）；
   上传失败时数据仍保存在浏览器本地，可在结果页导出 JSON。

> 隐私：摄像头画面只在浏览器本地处理，永不上传；上传的只有归一化注视坐标（0–1）、AOI 编码与行为反应。

## 数据分析

```bash
pip install -r requirements.txt

# 下载自己项目的数据（密钥保密，用环境变量）
#   PowerShell:  $env:HW2_KEY="你的密钥"
python fetch_data.py                       # → data/export_N2DRAL.json

# 分析 + 出图 + 报告
python analysis.py data/export_N2DRAL.json  # → results/report.md + 3 张 PNG
python analysis.py --demo 12                # 没有数据时用 12 人模拟数据跑通全流程
```

分析输出：被试级描述统计、2×2 重复测量方差分析（Flanker RT）、2D vs 3D 配对 t 检验、
3D 前景/后景单样本 t 检验（高估 / 低估）、AOI 停留时间，以及 `report.md` + PNG 图表。

## 仓库结构

```
FlankerPie/
├─ index.html        # 实验程序（单文件：刺激、流程、追踪、上传、可视化）
├─ vendor/webgazer/  # 自托管的眼动模型（不依赖第三方 CDN）
├─ analysis.py       # 数据分析：JSON/CSV → 统计检验 + 图表 + Markdown 报告
├─ fetch_data.py     # 从课程服务器导出本项目数据（密钥不进仓库）
├─ requirements.txt  # pandas / numpy / matplotlib / scipy
└─ results/          # 分析输出（gitignore，由 analysis.py 生成）
```

## 关于本项目

个人独立完成：实验设计、程序实现（HTML/CSS/JS）、数据采集与分析脚本、报告撰写均由本人完成。
如果后续有同学协作，可在此补充分工。

## 部署（GitHub Pages）

本仓库根目录已有 `index.html` 与 `.nojekyll`，可直接用 Pages 托管：

1. 仓库 **Settings → Pages → Build and deployment**：Source = `Deploy from a branch`，Branch = `main`，Folder = `/ (root)`，Save。
2. 等 1–2 分钟，页面顶部出现 *Your site is live at …*，地址形如 `https://<用户名>.github.io/FlankerPie/`。
3. 把这个地址换成上方「在线实验」那一行，并填到仓库右侧 **About → Website**。
4. 自己先跑一遍，确认末尾提示「✓ 数据已上传到课程服务器」。

> 注意：摄像头眼动必须在 `https://` 或 `http://localhost` 下才可用；`file://` 双击打开会自动降级为鼠标模式。
> `vendor/webgazer/`（约 18 MB）必须一起提交，否则页面无法加载眼动模型。

## 主要参考

- Eriksen, B. A., & Eriksen, C. W. (1974). Effects of noise letters upon the identification of a target letter in a nonsearch task. *Perception & Psychophysics, 16*(1), 143–149.
- Cleveland, W. S., & McGill, R. (1984). Graphical perception: Theory, experimentation, and application to the development of graphical methods. *Journal of the American Statistical Association, 79*(387), 531–554.
- Hulleman, J., & Olivers, C. N. L. (2017). The impending demise of the item in visual search. *BTP*, — （ flanker 距离操纵的理论背景）
- Kosinski, R. (2023). WebGazer.js: Eyetracking on the browser. *JOMS*.
