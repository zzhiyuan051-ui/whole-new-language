# 洄文字符集现状审计

> 由 `tools/char_audit.py` 直接解析字体文件生成，非人工填写。

## 一、字体文件

| 项 | 值 |
|---|---|
| 文件 | `font/GalHuiwen.ttf` |
| 大小 | 2,045,992 字节 |
| 字体名 | GalHuiwen / GalHuiwen Regular |
| 版本 | Version 1.0 |
| PostScript 名 | GalHuiwen-Regular |
| 字形数 | 3,001 |
| em 单位 | 1000 |
| 表 | GlyphOrder, OS/2, cmap, glyf, head, hhea, hmtx, loca, ltag, maxp, name, post |

## 二、码位占用（直接读 cmap）

| 项 | 值 |
|---|---|
| cmap 中已映射码位 | **3,000** |
| 最小 | U+E000 |
| 最大 | U+EBB7 |
| 私用区(BMP) 码位数 | **3,000**，跨度 U+E000–U+EBB7 |
| 私用区占用率 | **46.9%**（U+E000–U+F8FF 共 6400 位）|
| 私用区外的码位 | 0 |
| 连续段数 | 1 |

### 按 Unicode 区块归类

| 区块 | 码位数 |
|---|---:|
| Private Use Area | 3,000 |

### 私用区连续段

| 段 | 起 | 止 | 数量 |
|---|---|---|---:|
| 1 | U+E000 | U+EBB7 | 3,000 |

## 三、交叉校验（CSV vs 字体）

- CSV 声明的码位数：3,000
- 字体实际映射的码位数：3,000
- **一致性：通过**
