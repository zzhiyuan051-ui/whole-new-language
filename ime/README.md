# 洄文输入法

一个能直接下载使用的洄文打字工具。输入罗马字音节或汉字，出候选，选中上屏，
得到**洄文字形**，可以复制、可以导出成图片发给别人。

---

## 一、先说清楚它是什么、不是什么

**是**：一个桌面程序（Windows 独立 `.exe`，双击即用，不需要装 Python）。

**不是**：开箱即用的系统输入法。这个 exe **不会**在微信、Word、浏览器里接管键盘。
用法是「**在这里打好，复制走**」。

系统级输入法是另一份产物，在 [tsf/README.md](../tsf/README.md)：
TSF 文本服务已经编译并通过 COM 自检，但注册进语言栏要一次管理员确认
（Windows 只允许把输入法档案写进 HKLM）。钩子版免管理员，双击即用，
但不能进语言栏，对「以管理员运行的程序」也无效。

---

## 二、怎么用

### 打字

程序打开后，光标默认在顶部输入框里。三种输入方式都行：

| 你想打 | 输入 | 说明 |
| --- | --- | --- |
| 爱 | `za3` | **音节**：罗马字 + 声调数字 |
| 雨 | `yy4` | 同上 |
| 雨具 | `yy4 di6` 或 `yy4di6` | 多音节词，空格可有可无 |
| （不确定拼写） | `za` | **前缀**：列出所有 za 开头的音节 |
| （不知道洄文怎么写） | `爱` | **汉字反查**：直接打中文 |

候选出来后：
- 按 `1`–`9` 选第几个
- 按 `回车` 选第一个
- 或者**直接用鼠标点**候选方块

### 上屏与导出

- 选中的词会带着**字形**出现在「上屏」区，下面一行是逐词对照（汉字＋拼写）。
- **复制为图片**（推荐）：把上屏内容渲染成一张图（白色底、大字形、底下带中文意思）
  放进剪贴板。**在 QQ / 微信里 Ctrl+V 直接发，对方一定看得见** ——
  不要求对方装字体，也不受对方用的是什么程序影响。
- **复制洄文**：把上屏内容当**纯文字**复制。复制出去的是**私用区码位**。
  这条路限制很多，见下面「为什么发给别人必须用图片」。
- **导出 PNG**：同「复制为图片」，但存成文件。
- **导出 SVG**：矢量图，而且**内嵌了子集字体**，任何浏览器打开都能看到正确字形。
- **字表 / 词表**：浏览 3000 个词和字形，用来查字。

导出文件落在：程序目录下的 `洄文导出\` 文件夹（打包版）
或 `ime\output\`（源码版）。

> 输出目录是**按优先级试出来的**，不是写死的：exe 同目录 → 系统临时目录 → 用户主目录，
> 取第一个**真能写**的。因为实测在打包版里写 `~/Documents` 会拿到
> `PermissionError: [WinError 5] 拒绝访问`。

### 为什么发给别人必须用图片（实测结论，不是保守说法）

洄文用 Unicode 私用区（U+E000…U+EBB7）。私用区的含义是"谁都能用、但谁都不保证显示"。
对方的程序要显示它，必须**被明确告知**去用 `GalHuiwen`。实测：

| 程序类型 | 装了字体 | 能显示吗 |
| --- | --- | --- |
| 记事本等传统 Win32（走 GDI） | 是 | ✅ 能（GDI 的 FontLink 会回退到我们） |
| 记事本等传统 Win32 | 否 | ❌ 方格 |
| QQ / 微信新版 / 浏览器（Chromium 内核） | 是 | ❌ **照样方格** |
| QQ / 微信新版 / 浏览器 | 否 | ❌ 方格甚至空白 |

Chromium 是**故意**不对私用区做字体回退的
（见 chromium issue「Font code should not perform fallback character lookup
for personal use area codepoints」），所以**对方装不装字体都没用**。
除非明确指定 `font-family: GalHuiwen`（实测这样就能正常显示），否则 Chromium 一律不画。

结论：**纯文字只在部分传统程序里可见；要发消息，用「复制为图片」。**
图片对任何程序、任何人都成立。


### 键盘速查

| 键 | 作用 |
| --- | --- |
| `1`–`9` | 选第 N 个候选 |
| `回车` | 选第一个候选 |
| 鼠标点击候选 | 选那个候选 |

---

## 三、安装

### 打包版（推荐）

1. 下载 `洄文输入法.exe`
2. 放到任意目录，双击运行
3. 想放开始菜单就自己建个快捷方式（程序是单文件绿色版，不写注册表）

### 源码版

以下命令都在**仓库根目录**执行（克隆下来后，`ime/` 就在根目录下）。

```powershell
# 需要 Python 3.10+ 和两个第三方库
pip install -r requirements.txt      # 或：pip install pillow fonttools

# 直接跑
python ime/app.py

# 无界面自检（验证数据、引擎、导出都正常）
python ime/selftest.py
```

### 自己重新打包 exe

**必须用 `--onedir`，不要用 `--onefile`。** 原因见下面「打包踩到的两个坑」。

```powershell
# 先装 PyInstaller（只有打包时需要）
pip install pyinstaller

$ws = (Get-Location).Path     # 仓库根目录

python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "洄文输入法" `
  --icon "$ws\font\GalHuiwen.ico" `
  --distpath "$ws\dist" --workpath "$ws\build" --specpath "$ws\build" `
  --add-data "$ws\lexicon.tsv;." `
  --add-data "$ws\characters.json;." `
  --add-data "$ws\tools\syllabary.tsv;tools" `
  --add-data "$ws\font\GalHuiwen.ttf;font" `
  --hidden-import fontTools.subset --hidden-import fontTools.ttLib `
  --hidden-import PIL._tkinter_finder `
  "$ws\ime\app.py"

# 打包后打发布包（zip）
python ime/make_release.py
```

### 打包踩到的两个坑

**坑一：`--onefile` 在本机起不来。**

单文件版要在运行时把内容解到临时目录，实测报：

```
[PYI-38696:ERROR] Could not create temporary directory!
```

排查过：`TEMP` 存在且可写、子进程也能用 Python 建临时目录、
清掉 31 个残留 `_MEI*` 目录后仍然失败；但把 `TEMP` 指到工作区内就能跑。
结论是单文件模式在这个环境下不可靠 —— **改用 `--onedir` 后一次通过**
（不落地解包，从根上绕开）。

**坑二：窗口版 exe 没有 stderr，出错看起来就是「卡住」。**

`--windowed` 不分配控制台，异常会被吞掉或弹一个没人点的对话框。
所以 `app.py` 里加了 `_crash_report()`：任何未捕获异常都写进
`崩溃报告.txt`（和导出文件同目录），否则没法排查。

**另外**：直接用 `Start-Process` 启动 GUI 会占住调用方的输出管道，
在自动化脚本里表现为「命令挂住」。要验证界面请用 `--selftest`
（无人值守）或 `--screenshot`（截一张真界面图后自动退出），不要裸启动。

---

## 四、文件说明

| 文件 | 作用 |
| --- | --- |
| `app.py` | 界面（tkinter）。字形用 PIL 渲染成图片贴上去 |
| `engine.py` | 输入引擎：音节/汉字 → 候选词。与界面无关，可单独用 |
| `paths.py` | 路径解析。源码运行与打包成 exe 两种情形都靠它找对文件 |
| `selftest.py` | 自检：数据文件、引擎、上屏、导出逐项验证 |
| `make_release.py` | 把打包产物 + 文档 + 独立字体 + 截图拼成可下载的 zip |
| `output/` | 导出的图片、界面截图、自检报告 |

### 三种运行模式

| 命令 | 作用 |
| --- | --- |
| （不带参数） | 正常开界面 |
| `--selftest` | 无人值守自检，结果写 `自检报告.txt`，退出码表达成败 |
| `--screenshot` | 真建窗口、自动打字上屏、截一张界面图、退出 |

```powershell
python ime/app.py --selftest      # 验证功能
python ime/app.py --screenshot    # 验证界面长什么样
```

后两个模式是给自动化用的 —— GUI 进程会占住输出管道，裸启动会「挂住」。

### 字形为什么用图片显示

界面里的字形是 PIL 直接把 `GalHuiwen.ttf` 画成图片贴上去的。
这样不依赖「这个进程有没有把字体注册进 GDI」，离线、跨机器都一样能看见。

字体本身**已经能装成系统字体**。根因曾经是码位从 `U+E000 + 字形编号` 算，
3000 个已定义字的编号并不连续，末码位冲出 BMP（`U+FFFF`），GDI 整份拒收。
改成按编号排序后依次分 `U+E000` 起的连续私用区码位之后，
`AddFontResourceEx` 返回 1，`GetTextFaceW` 选中的是 `GalHuiwen` 而不是宋体。
安装与验证：

```powershell
python tools/hwfontinstall.py install
python tools/hwfontinstall.py verify
```

---

## 五、依赖

| 用途 | 依赖 |
| --- | --- |
| 界面 | `tkinter`（Python 自带） |
| 字形渲染 | `Pillow` |
| 导出 SVG（子集化字体） | `fontTools` |
| 打包 exe | `pyinstaller` |

打包版 exe 已经把前三个都打进去了，用户不需要装任何东西。
