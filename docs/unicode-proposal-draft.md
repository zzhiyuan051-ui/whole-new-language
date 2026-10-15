# 洄文编码提案（Unicode / ISO 10646）— 初稿骨架

> **文档状态：草案 v0.1，未提交。**
> 本文件按 UTC Script Encoding Working Group（SEW）官方《Submission Guidelines and Process》
> 的逐条要求组织。**标注 `【待补】` 的段落是当前无法成立的部分，不要删除标注就提交。**
>
> 官方要求来源：<https://sew.unicode.org/guidelines>（`《Submission Guidelines and Process》`
> 的实际地址，2026-10 实测可访问；**`unicode.org/guidelines` 是 404 的旧地址，勿引用**）
> 提案必须是**单个 PDF**，通过 <https://sew.unicode.org/submission> 提交，且提交前必须签 CLA。

---

## 0. 提案基本信息

| 字段 | 值 |
|---|---|
| 提案名称 | Proposal to encode the Huiwen script（洄文） |
| 脚本名（英文） | Huiwen |
| 脚本名（中文） | 洄文 |
| 提交人（Submitter） | 【待填：真实姓名 + 可验证邮箱】 |
| 作者（Authors） | 【待填：全部作者，**每人都要签 CLA**】 |
| 潜在知识产权人（IP claimants） | 【待填：见 §9，**本项目必然适用**】 |
| 目标码位 | 尚未申请；当前实现自用 U+E000–U+EBB7 |
| 字符数 | 3,000（已定义）／15,000（字形空间已成形） |
| 配套字体 | `GalHuiwen.ttf` v1.0，em=1000，3,001 字形 |
| 附带的 ISO/IEC 10646 摘要表 | 【待填：模板见 <https://www.unicode.org/L2/summary.html>】 |

---

## 1. 摘要（Summary of Request）

本提案请求为「洄文」这一**自源、表意、字形可程序生成**的书写系统编码字符。

洄文的核心设计特征是：**字形不是一个一个画出来的，而是由编号经固定算法生成的**
（`字形 = f(编号)`）。编号译为基-4 的八个数字位，落在 4×5 字格上；边框承担可心算的
校验（`边框 = 编号 mod 3`）；中央格承载语义类；字格四角承载「家族纹」，用于提升
近形字的视觉区分度。

截至本草案，洄文有 3,000 个已定义字符（有音、有义、有字形），并已实现
Windows TSF 输入法与真字体。

**【待补】本提案请求的具体内容**：请在此明确写出是以下哪一种，二者是**根本不同的编码策略**，
不可含糊（见 §4.3）：

- 策略 A：为 3,000 个**字符整体**编码（每个字一个码位）；
- 策略 B：只编码**构字组件**（八个数位、边框类型、中央类标记、家族纹），
  由渲染层按算法组合成字（类似谚文 Jamo 的思路）。

---

## 2. 相关既有文档（Reference to Prior Documents）

**本项目目前没有向 UTC 文档登记处提交过任何文件。**

【待补】若之后在 SEW / UTC / WG2 有过任何往来（包括初步询问的回复），
请在此列出文档编号（形如 `L2/xx-xxx`、`WG2 Nxxxx`）。官方要求提案引用
[文档登记处](https://www.unicode.org/L2) 中的相关既有文档。

---

## 3. 脚本介绍（Introduction）

> 官方要求：*introduction to the proposed script or characters, **citing modern sources of information***。
> 「modern sources」指可被第三方查证的公开出版物/网站/学术文献 —— **不是作者自述**。

### 3.1 语言与文字的关系

洄文是**人造语言 + 自源文字**。其与自然语言最根本的分岔在于：

| | 洄文 | 汉语／英语 |
|---|---|---|
| 字形来源 | 坐标编码生成（字形是编号的函数） | 约定俗成 |
| 形与音 | **完全无关** | 汉字部分表音；字母文字表音 |
| 语法单位 | 句子是**有向图**：词根是结，关系是弓 | 词按线性排列 |

### 3.2 音系（供属性与排序参考）

音系为 **13 声基 × 8 腔 × 6 调 = 624 个合法音节**。
词表实际用到 3,000 个**不同音节串**（多数为双音节派生词）。

【待补】音系规范文件 `spec/03-phonology.md` 的**公开可访问链接**（若放上 GitHub 等公开仓库）。

### 3.3 字形结构（这是本提案的技术核心）

字格为 **4 列 × 5 行**，共 20 格，其中：

- **八个数字位**：编号的基-4 展开，每位取 0–3；
- **边框校验**：`边框 = 编号 mod 3`，由 `4^k ≡ 1 (mod 3)` 保证「一位数字写错，边框立刻对不上」；
- **中央格**：语义类（44 类之一）；
- **四角家族纹**：8 式（空角／点角／双点角／环角／横角／方角／叉角／角角），
  把可辨外形从 `3 边框 × 20 中央标记 = 60` 提升到 `60 × 8 = 480`。

字形空间为 `4⁸ = 65,536`；本表成形 **15,000** 个。

### 3.4 字符集现状（数据源：字体 cmap，可复算）

| 项 | 值 | 来源 |
|---|---|---|
| 已定义字符 | **3,000** | `font/GalHuiwen.ttf` cmap |
| 码位范围 | **U+E000 – U+EBB7**（连续 1 段，3,000 位） | 同上 |
| 是否全在私用区 | **是**（BMP 私用区，占 6,400 位的 46.9%） | 同上 |
| 私用区外码位 | **0** | 同上 |
| 备用（已成形待指派）字 | 12,000 | `characters.tsv` |
| 字形空间余量 | 65,536 | `spec/01-script.md` |
| 覆盖率 | 44 个语义类中，**20 类**有已定义字符；**24 类**仅有备用字 | `characters.tsv` |

> 复算命令：`python tools/char_audit.py` 与 `python tools/codepoint_table.py`

### 3.5 【待补】现代来源引用

必须列出**第三方可查证**的来源。目前本项目的全部材料都在作者本机，
不满足「modern sources」这一条。最低要求：

- [ ] 公开仓库（GitHub / Gitee）URL
- [ ] 《洄文大字典》与《洄文入门》的公开可访问地址
- [ ] 若有：任何第三方报道、评测、学术引用、社群讨论存档

---

## 4. 与既有字符的比较（Comparison to Existing Characters）

> 官方要求：*comparison to existing characters that are visually similar, if any*。
> 并且必须说明**是否考虑过用既有 Unicode 字符序列表示**，以及拒绝的理由。

### 4.1 视觉相近的既有字符

【待补】洄文的骨架是「框 + 格内数位点」，与以下既有字符在视觉上有一定相似度，
需要逐项说明**可区分性**：

- **CJK 部首/部件**（如 囗 U+56D7、冂 U+5182）—— 仅外形相似，语义无关；
- **制表符与几何图形**（U+2500 段、U+25A0 段）—— 洄文的框与点可能被误认；
- **Yi Syllables**（U+ A000 段）与 **Nushu**（U+1B170 段）—— 同为「成套的表意/音节文字」，
  是最直接的可比对象，需要说明为何洄文不能映射到它们；
- **私用区既有占用** —— 见 §4.2。

### 4.2 关于私用区（PUA）的说明 —— 这是本提案必须正面回答的一节

现行 `GalHuiwen.ttf` 把 3,000 个字符放在 **U+E000–U+EBB7**。
Unicode 官方 FAQ 对私用区的定义是：

> Private-use characters ... whose interpretation is not specified by a character encoding
> standard and whose use and interpretation **may be determined by private agreement
> among cooperating users**.
> —— <https://www.unicode.org/faq/private_use.html>

因此必须如实说明：

1. **私用区码位不是稳定标识**：同一码位在不同字体/不同约定下含义完全不同。
   微软雅黑、思源黑体、日文 legacy 字体都可能占用 U+E000 段。
2. **跨设备互传会失败**：把洄文文本发给未装本字体的接收方，对方看到的是
   豆腐块或其他字体的无关字形 —— 因为传输的是码位，不是字形。
3. **这正是本提案的理由，而不是反例**：申请正式编码的目的就是让洄文拥有
   **全局唯一、跨系统稳定**的码位。

【待补】建议同时说明是否已在
[ConScript Unicode Registry](http://www.evertype.com/standards/csur/) 登记私用区占用，
以及是否需要调整占用区间以避免与他人冲突。

### 4.3 关键设计问题：整体编码 还是 组件编码

**这是本提案成败的第一个技术决策，必须在提交前定下来。**

| | 策略 A：整体编码 | 策略 B：组件编码 |
|---|---|---|
| 编码对象 | 每个字一个码位 | 八个数字位 + 边框 + 类标记 + 家族纹 |
| 码位需求 | 3,000（现）→ 15,000（满） | 约 8×4 + 3 + 44 + 8 ≈ 87 个 |
| 优点 | 字即码位，文本模型最简单 | 码位需求极小，与「字形由编号生成」的设计一致 |
| 缺点 | 15,000 个表意字符的**使用证据门槛极高** | 需定义组合/渲染规则；与「字符 vs 字形」的官方区分存在冲突风险 |
| 官方风险 | 需证明 15,000 个**都是独立字符** | 官方明确警惕「可用既有序列表达的重复表示」 |

官方对这条有明确警示：

> Often a proposed character can be expressed as a sequence of one or more existing
> Unicode characters. Encoding a character that can be represented by a sequence would
> be a **duplicate representation**, and is thus not suitable for encoding.

**注意**：这一条针对的是「用既有 Unicode 字符可以组合出来」的情况。
洄文的组件是**自创的、无既有 Unicode 对应物**，所以策略 B 并非直接违反该条；
但必须论证**为什么用户读到的是一个字符、而不是一串组件**。
如果洄文的读者在心理上是「看到 8 个数位拼成一个字」，策略 B 就成立；
如果是「一个不可拆的整体字形」，则应走策略 A 并准备承担 15,000 字符的举证责任。

【待补】选定策略并写出论证。

---

## 5. 建议字符属性（Suggested Character Properties）

> 官方要求：至少需要 `UnicodeData.txt` 所需的值。参考
> [Unicode Properties in Character Proposals](https://www.unicode.org/pending/properties.html)。

以下为**按既有表意文字先例给出的建议值**，未经 UTC 确认，属于提案方意见：

| 属性 | 建议值 | 依据 |
|---|---|---|
| `General_Category` | `Lo`（Letter, other） | 隶书、女书、西夏文等表意/音节文字均为 `Lo` |
| `Script` | `Huiwen`（需新建脚本码，提案时一并申请） | 新脚本 |
| `Block` | 建议新建 `Huiwen` 区块（名称与范围待定） | 3,000–15,000 字符无法塞进现有区块 |
| `Bidi_Class` | `L` | 左起横排 |
| `Line_Break` | `ID`（Ideographic） | 允许任意字间换行 |
| `East_Asian_Width` | `W`（Wide） | 字形占满字格，方形 |
| `Numeric_Type` | `None` | 洄文有独立的数词（见词表 `pos=num`），字形本身不表数 |
| `Ideographic` | `Y` | 表意文字 |
| `Unified_Ideograph` | **`N`** | **不是汉字，不得纳入 Unihan 统一** |
| `Case_Folding` / `Simple_Lowercase_Mapping` | 无 | 无大小写 |
| `Decomposition` | **`None`** | 洄文字符不可拆解为其他 Unicode 字符 |
| `Joining_Type` | `U`（Non-joining） | 无连写 |
| `Combining_Class` | `0`（Not_Reordered） | 不做组合字符，除非采用 §4.3 策略 B |
| `Word_Break` | 需专门定义 | **【待补】洄文是图上语法，「词」的切分规则必须写清楚** |

可复算的逐字符属性表生成脚本：**【待补】**（模板可直接由
`tools/codepoint_table.py` 的产出改写）。

---

## 6. 字符排序（Preferred Ordering）

> 官方要求：*preferred ordering of proposed characters — how would words be ordered
> in a dictionary?*

洄文字表已经有两套现成排序，提案需选定其一并论证：

1. **按字形编号**（`glyph` 升序）—— 即当前的 U+E000 起顺排。
   优点：与「字形 = f(编号)」一致，可程序生成。
   缺点：对人不友好，相邻码位在语义上无关。
2. **按语义类 + 类内序**（`class_no`, 类内编号）—— 与人读词典一致。
   优点：符合「中央格一眼看出在谈什么」的设计意图，字典顺序直观。

【待补】明确选定，并给出**排序键的完整定义**（评审会要求可机械复现）。

---

## 7. 标点、断行与分词行为

> 官方要求（新脚本必备）：*information about punctuation and line and word breaking behavior*。

【待补】至少需要回答：

- 洄文使用既有 Unicode 标点（，。？！）还是自创标点？
- 自创标点是否也要编码？（若是，需单独举证）
- 断行规则：能否在任意字符间断行？有无禁则（行首/行尾禁忌）？
- **分词规则**：洄文语法是关系图，「词」的边界由什么确定？
  这直接影响 `Word_Break` 属性与所有文本处理工具。
- 数字与外来词如何混排？

---

## 8. 用于 Core Specification 的章节草稿

> 官方要求（新脚本必备）：*suggested text for the introductory chapter about the script
> to be included in the Core Specification*。

【待补】需要写成**英文**、按 UAX 行文风格、可直接嵌入 Unicode Standard 核心规范的段落。
内容涵盖：脚本名与别名、书写方向、字形结构、音节结构、与汉语的关系、排序规则。

---

## 9. 字体与许可（Font）—— 这条是硬门槛

官方原文：

> We require a font with an appropriate license for publishing the standard ...
> **The Script Encoding Working Group will not recommend any proposals to the UTC
> without an appropriate font in place.**

| 项 | 现状 |
|---|---|
| 字体文件 | ✅ `font/GalHuiwen.ttf`（3,001 字形，em=1000） |
| 是否覆盖提案的全部字符 | ✅ 3,000 / 3,000 |
| 是否符合 [Font Submission Policy](https://www.unicode.org/policies/font_policy.html) | **【待补】必须逐条核对** |

【待补】关键问题：Font Submission Policy 通常要求字体以允许 Unicode Consortium
**再分发与出版**的许可提供。当前 `GalHuiwen.ttf` 的许可状态需要明确声明。

---

## 10. 法律与 CLA（Legal & Licensing）—— 本项目必然适用

官方原文（**这一条对洄文是直接命中的**）：

> **IP Claimants in Scripts & Characters** ... if there are any persons or entities who have,
> may have, or claim intellectual property rights ... in a proposed character or script itself,
> then the Consortium requires two things: (i) that they sign a Unicode CLA or other
> appropriate license agreement, and (ii) that they provide a formal written endorsement
> of the proposal.
>
> **The Consortium will not consider proposals that are not endorsed in writing by all
> IP claimants in the proposed characters/scripts.**

对洄文的具体含义：

| 要求 | 谁来做 | 状态 |
|---|---|---|
| 所有**作者**签 CLA | 提案的每一位作者 | 【待补】 |
| 提交人签 CLA（提交前必须） | 提交人 | 【待补】 |
| **IP 权利人书面背书** | 洄文的著作权人（＝作者本人，若无可争议） | 【待补】 |
| 在提案中**申报**全部潜在 IP 权利人 | 提交人 | 【待补】 |

> ⚠️ 洄文是**一人创作的原创文字**，属于官方描述的
> "created scripts ... in which the script creator expressly claims copyright" 情形。
> 官方对此的态度是「先签 CLA + 书面背书，否则不予考虑」——**不是不能编，是先理清权利**。
>
> 有一条反过来要利用：**如果著作权人就是你自己，你只需要自己签字背书**。
> 这是你可以完全控制的环节，不要拖到最后。

【待补】明确声明：洄文著作权归属、是否登记过软件著作权/作品著作权、是否声明放弃部分权利。

---

## 11. 三条受理标准 —— 现状如实评估

官方原文：

> For proposed new scripts and characters, three basic criteria need to be met:
> 1. **Usage**: you need to demonstrate that the characters are **already in use by a
>    community (independent of the script creator, if applicable)**
> 2. **Stability**: ... the proposed repertoire of characters, including the characters
>    themselves, is **stable and not in active development**
> 3. **Need for interchange**: ... needed for **public interchange of information in plain text**

| 标准 | 现状 | 判定 |
|---|---|---|
| **1. 使用（独立于创作者）** | 除作者外无已知使用者 | ❌ **不满足 —— 当前唯一的拦路石** |
| **2. 稳定性** | 3000 词表与字形算法已冻结；但 **44 类中 24 类仍为零定义、12000 备用字待指派** | ⚠️ **部分满足**：已编码的 3,000 个稳定，但整体字符集**明显仍在开发中** |
| **3. 交换需求** | 目前无跨系统交换场景（仅本机 + 自建输入法） | ❌ 不满足 |

### 结论（如实）

**现在提交会被退回，而且是 desk rejection（不予讨论、不公开发表）。**
理由不是洄文不好，而是三条标准里两条不成立 —— 尤其第 1 条被官方明确限定为
「**independent of the script creator**」，一个人自用**在定义上**就不构成 usage 证据。

**因此，在拿到独立使用者之前，提案不应该提交。**
本文件的价值是：把除了「使用证据」之外的一切**提前做完并冻结**，
这样等使用者出现时，可以在最短时间内交出一份完整提案 —— 而完整度本身
是 SEW 是否愿意投入时间的关键。

---

## 12. 提交前的检查清单

- [ ] §4.3 编码策略（整体 / 组件）已选定并有论证
- [ ] §5 属性表已生成为可复算文件
- [ ] §6 排序键已定义
- [ ] §7 标点与分词规则已写清
- [ ] §8 Core Specification 章节草稿已写为英文
- [ ] §9 字体许可已确认符合 Font Submission Policy
- [ ] §10 全部作者签 CLA、IP 权利人出具书面背书
- [ ] §3.5 第三方可查证的公开来源已就位
- [ ] §11 标准 1「独立使用社群」有证据（**当前未达成**）
- [ ] 全部内容合并为**单个 PDF**
- [ ] 通过 <https://sew.unicode.org/submission> 提交

---

## 13. 官方入口速查（均为 2026-10 实测）

| 用途 | 地址 |
|---|---|
| 提交指南（本文件依据） | <https://sew.unicode.org/guidelines> |
| 提交表单（需邮箱登录） | <https://sew.unicode.org/submission> |
| 工作组主页 | <https://sew.unicode.org> |
| UTC 文档登记处 | <https://www.unicode.org/L2> |
| 已提案字符进度表（避免重复） | <https://www.unicode.org/alloc/Pipeline.html> |
| **被否决提案档案（提交前必查）** | <https://www.unicode.org/alloc/nonapprovals.html> |
| ISO 流程阶段说明 | <https://www.unicode.org/alloc/ISOStages.html> |
| 私用区 FAQ | <https://www.unicode.org/faq/private_use.html> |
| 字体提交政策 | <https://www.unicode.org/policies/font_policy.html> |
| 字符属性指南 | <https://www.unicode.org/pending/properties.html> |
| ISO 10646 摘要表模板 | <https://www.unicode.org/L2/summary.html> |
| 先期评审（另一条路） | Script Encoding Initiative，<https://sei.berkeley.edu/> |
| 私用区登记（非官方） | ConScript Unicode Registry，<http://www.evertype.com/standards/csur/> |

> 注：早期资料中常见的 `https://www.unicode.org/guidelines` 与
> `https://www.unicode.org/pending/proposals.html` 两条链接**当前均已 404**
> （后者会跳转 sew.unicode.org）。引用时请用上表地址。
