#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 语法内核：线性形式 → 关系图 → 校验（spec/02-grammar.md 的可执行实现）

线性形式（ASCII）文法
---------------------------------------------------------------
  结声明    @<id> <词根>[.<换声>]
  回指结    @<id> ..<原id>
  临弓      <起> -> <终>          默认按槽表顺序填位
            <起> -<位>-> <终>     显式指定位（甲/乙/丙/丁/戊/己/庚）
  饰弓      <修> => <被修>
  结际弓    <起> <<|>>|+>|?>|<>|!>|#> <终>      先/后/因/若/虽/目的/于是
  子图端点  [ <图> ]              方括号内是一张完整子图，整体当端点
  模态      ? / ~ / !             行首罩全图
  义标      #see #hear #felt #infer #hearsay #common #imagine #dream
  注释      // 之后忽略
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

ROLES = ["甲", "乙", "丙", "丁", "戊", "己", "庚"]
ROLE_ALIAS = {"A": "甲", "B": "乙", "C": "丙", "D": "丁", "E": "戊", "F": "己", "G": "庚"}
VOICE_ALIAS = {"n": "体", "a": "貌", "v": "用", "d": "度", "l": "场",
               "体": "体", "貌": "貌", "用": "用", "度": "度", "场": "场"}
JIE_MARKS = {"<<": "先", ">>": "后", "+>": "因", "?>": "若", "<>": "虽",
             "!>": "目的", "#>": "于是"}
EVIDENCE = {
    "#see": "亲见", "#hear": "亲闻", "#felt": "亲历", "#infer": "推知",
    "#hearsay": "传闻", "#common": "常识", "#imagine": "想象", "#dream": "梦",
}
MODALS = {"?": "询", "~": "否", "!": "祈"}


# ---------------------------------------------------------------- 数据结构
@dataclass
class Node:
    id: str
    root: str = ""
    voice: str = "体"
    ref: str | None = None          # 回指目标
    syll: str = ""
    zh: str = ""
    index: int | None = None

    @property
    def is_ref(self) -> bool:
        return self.ref is not None


@dataclass
class Relation:
    kind: str                       # lin / shi / jie
    src: str | None = None          # 简单端点：结 id
    dst: str | None = None
    src_sub: "Graph | None" = None  # 子图端点
    dst_sub: "Graph | None" = None
    role: str = ""                  # 临弓的位
    mark: str = ""                  # 结际弓记号
    slot_order: int = -1            # 默认槽序（用于回填 role）


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    rels: list[Relation] = field(default_factory=list)
    modal: str = ""
    evidence: str = ""
    source_text: str = ""
    title: str = ""

    def add(self, n: Node) -> None:
        self.nodes[n.id] = n
        self.order.append(n.id)

    def lin_targets(self, src: str) -> list[Relation]:
        return [r for r in self.rels if r.kind == "lin" and r.src == src]

    def flat(self, keep_inner: bool = False) -> "Graph":
        """主图视图：只保留本图自己的结与它们之间的弓。

        子图（方括号）里的结与弓不属于本图——它们是被当作端点用的**另一张图**。
        keep_inner=True 时把子图**内部**的弓也带进来（渲染子图本身时用得到），
        但仍不把它们混进主图的关系里。
        """
        hidden: set[str] = set()
        children: list[Graph] = []
        for r in self.rels:
            for sub in (r.src_sub, r.dst_sub):
                if sub is not None and sub not in children:
                    children.append(sub)
                    hidden |= set(sub.order)
        g = Graph(source_text=self.source_text, title=self.title,
                  modal=self.modal, evidence=self.evidence)
        for nid in self.order:
            if nid not in hidden:
                g.add(self.nodes[nid])
        for r in self.rels:
            if r.kind == "_bridge":
                continue
            if r.src in hidden or r.dst in hidden:
                continue
            g.rels.append(r)
        if keep_inner:
            for sub in children:
                g.rels.extend(sub.rels)
                g.nodes.update({k: v for k, v in sub.nodes.items() if k in hidden})
                g.order.extend([k for k in sub.order if k not in g.order])
        return g


# ---------------------------------------------------------------- 词表挂接
def load_lexicon(path: Path) -> dict[str, dict]:
    by_syll: dict[str, dict] = {}
    if not path.exists():
        return by_syll
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rec = dict(zip(head, f))
        by_syll[rec["syll"]] = rec
    return by_syll


def attach(graph: Graph, lex: dict[str, dict]) -> None:
    for nid in graph.order:
        n = graph.nodes[nid]
        if n.is_ref:
            tgt = graph.nodes.get(n.ref)
            if tgt:
                n.root, n.voice = tgt.root, tgt.voice
                n.syll, n.zh, n.index = tgt.syll, tgt.zh, tgt.index
            continue
        rec = lex.get(n.root)
        if rec:
            n.syll = rec["syll"]
            n.zh = rec["zh"]
            n.index = int(rec["index"])


def slots_of(lex: dict[str, dict], root: str) -> list[str]:
    rec = lex.get(root)
    if not rec:
        return ["甲", "乙"]
    return list(rec.get("slots") or "甲乙")


# ---------------------------------------------------------------- 解析
NODE_RE = re.compile(r"^@(?P<id>[A-Za-z0-9_]+)\s+(?![->=])(?P<rest>.+)$")
TOK = r"(?:@?[A-Za-z0-9_]+|\[.*?\])"
JIE_RE = re.compile(rf"^(?P<a>{TOK})\s+(?P<mark><<|>>|\+>|\?>|<>|!>|#>)\s+(?P<b>{TOK})$")
LIN_RE = re.compile(
    rf"^(?P<a>{TOK})\s+(?:-(?P<role>[甲乙丙丁戊己庚]|[A-G])->|->)\s+(?P<b>{TOK})$")
SHI_RE = re.compile(rf"^(?P<a>{TOK})\s+=>\s+(?P<b>{TOK})$")


def _endpoint(graph: Graph, tok: str, errors: list[str]):
    """端点记号 → ('node', id) 或 ('sub', Graph)。

    子图端点写作 `[ ... ]`（可含空格，故此处按配对括号切分而非按词切分）。
    """
    tok = tok.strip()
    got = _split_sub(tok)
    if got is not None:
        sub_text, rest = got
        if rest:
            errors.append(f"子图端点后有多余记号：{rest!r}")
        sub = parse(sub_text)
        errors.extend(getattr(sub, "parse_errors", []))
        _merge_sub(graph, sub, errors)
        # 注意：子图内部的弓不并入本图——它们属于子图，由 link_subgraphs 处理
        return ("sub", sub)
    m = re.match(r"^@?([A-Za-z0-9_]+)(\.\.@?([A-Za-z0-9_]+))?$", tok)
    if not m:
        errors.append(f"无法解析端点：{tok!r}")
        return (None, None)
    nid, _, ref = m.group(1), m.group(2), m.group(3)
    if nid not in graph.nodes:
        errors.append(f"弓指向未声明的结：{nid!r}")
        return (None, None)
    return ("node", nid)


_SUBSEQ = [0]


def _merge_sub(graph: Graph, sub: "Graph", errors: list[str] | None = None) -> None:
    """把子图的结与弓并入本图，并给子图的结标号加作用域前缀。

    结标号在**一张图内**唯一，不是全局唯一——子图与主图各用 @0、@1 是正常的。
    并入时必须加前缀，否则两张图里同号的结会被错误地合并成一个
    （这类错误会静默地把两个结变成一个，所以这里显式堵住）。
    """
    _SUBSEQ[0] += 1
    pfx = f"s{_SUBSEQ[0]}_"
    remap: dict[str, str] = {}
    for nid in sub.order:
        new = pfx + nid
        if new in graph.nodes:
            if errors is not None:
                errors.append(f"子图结标号冲突：{new!r}")
            continue
        remap[nid] = new
        n = sub.nodes[nid]
        n.id = new
        if n.ref:
            n.ref = pfx + n.ref
        graph.nodes[new] = n
        graph.order.append(new)
    for r in sub.rels:
        r.src = remap.get(r.src, r.src) if r.src else r.src
        r.dst = remap.get(r.dst, r.dst) if r.dst else r.dst
        graph.rels.append(r)
    sub.order = [remap.get(i, i) for i in sub.order]
    # 子图自己的字典也要跟着改名，否则它后面再被引用时找不到自己的结
    sub.nodes = {remap.get(k, k): v for k, v in sub.nodes.items()}


def _split_sub(line: str) -> tuple[str, str] | None:
    """若本行以 [ 起、含配对的 ]，返回（括号内内容, 其后的剩余）。支持嵌套。"""
    if not line.startswith("["):
        return None
    depth = 0
    for i, ch in enumerate(line):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return line[1:i], line[i + 1:].strip()
    return None


def _add_sub(graph: Graph, sub_text: str, errors: list[str]) -> "Graph":
    """把方括号里的源文本当作一张子图：结加上作用域前缀后并入本图，弓并入本图。"""
    sub = parse(sub_text)
    errors.extend(getattr(sub, "parse_errors", []))
    _merge_sub(graph, sub, errors)
    return sub


def link_subgraphs(g: Graph) -> None:
    """把「子图整体当端点」在图上落到实处：子图各结与对端连边。

    这不是额外的语法——端点既然是一个整体，它与对端之间就存在这条连线；
    它让「不连通」的校验能正确覆盖子图。
    """
    for r in g.rels:
        if r.kind == "_bridge":
            continue
        for sub, other in ((r.src_sub, r.dst), (r.dst_sub, r.src)):
            if sub is None or other is None or other not in g.nodes:
                continue
            for nid in sub.order:
                if nid != other:
                    g.rels.append(Relation(kind="_bridge", src=nid, dst=other))


_TOKEN_RE = re.compile(
    r"\[|\]|@[A-Za-z0-9_]+|\.\.[A-Za-z0-9_]+|=>|->|<<|>>|\+>|\?>|<>|!>|"
    r"#[A-Za-z]+|"                      # 义标 #see / #hearsay …（须排在 #> 之前）
    r"#>|"
    r"-[甲乙丙丁戊己庚A-G]->|"
    r"[^\s\[\]]+")

def _tokenize(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        if not line:
            continue
        out.extend(_TOKEN_RE.findall(line))
    return out


ROLE_OP_RE = re.compile(r"-[\u7532\u4e59\u4e19\u4e01\u620a\u5df1\u5e9aA-G]->")


def _is_op(tok: str) -> bool:
    """是不是一个关系记号（而非词根）。显式记号表，不靠字符串前缀猜。"""
    return (tok in ("->", "=>") or tok in JIE_MARKS
            or bool(ROLE_OP_RE.fullmatch(tok)))


def _parse_tokens(toks: list[str], errors: list[str]) -> Graph:
    """记号流 → 图。子图靠括号配对，所以嵌套与「一行多句」都天然支持。"""
    g = Graph()
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t in MODALS:
            g.modal = MODALS[t]
            i += 1
            continue
        if t in EVIDENCE:
            g.evidence = EVIDENCE[t]
            i += 1
            continue
        # 结标号在源文里写作 @x，在内部一律不带 @；关系端点在此统一归一
        if t.startswith("@") and i + 1 < n and _is_op(toks[i + 1]):
            t = t[1:]        # 子图：[ ... ] <记号> <终点>   —— 子图整体当端点
        if t == "[":
            depth, j = 1, i + 1
            while j < n and depth:
                depth += (toks[j] == "[") - (toks[j] == "]")
                j += 1
            sub = _parse_tokens(toks[i + 1:j - 1], errors)
            rest = toks[j:] if j < n else []
            _merge_sub(g, sub, errors)
            if rest and _is_op(rest[0]):
                op = rest[0]
                target = rest[1].lstrip("@") if len(rest) > 1 else None
                if op == "=>":
                    g.rels.append(Relation(kind="shi", src_sub=sub, dst=target))
                elif op in JIE_MARKS:
                    g.rels.append(Relation(kind="jie", mark=JIE_MARKS[op],
                                           src_sub=sub, dst=target))
                else:
                    role = ROLE_ALIAS.get(op[1:-2], op[1:-2]) if op.startswith("-") else ""
                    g.rels.append(Relation(kind="lin", role=role,
                                           src_sub=sub, dst=target))
                i = j + 2
                continue
            i = j
            continue
        # 关系放在**结声明之前**判断：源文里关系写作 `<起点> <记号> <终点>`，
        # 起点同样带 @ 前缀（如 `@1 -> 0`）。若先认结声明，`@1` 会被当成
        # 「缺词根的结」而只推进一位，后面的 `->` 就再也配不上两端了。
        if i + 1 < n and _is_op(toks[i + 1]):
            op = toks[i + 1]
            dst = toks[i + 2].lstrip("@") if i + 2 < n else None
            if op == "=>":
                g.rels.append(Relation(kind="shi", src=t, dst=dst))
            elif op in JIE_MARKS:
                g.rels.append(Relation(kind="jie", mark=JIE_MARKS[op], src=t, dst=dst))
            else:
                role = ROLE_ALIAS.get(op[1:-2], op[1:-2]) if op.startswith("-") else ""
                g.rels.append(Relation(kind="lin", role=role, src=t, dst=dst))
            i += 3
            continue
        # 结声明：@<标号> <词根>[.<换声>]  或  @<标号> ..<原标号>
        if t.startswith("@"):
            nid = t[1:]
            body = toks[i + 1] if i + 1 < n else ""
            if body.startswith(".."):
                g.add(Node(id=nid, ref=body[2:]))
                i += 2
                continue
            if body and not body.startswith("@") and body != "[" and not _is_op(body):
                parts = body.split(".")
                g.add(Node(id=nid, root=parts[0],
                           voice=VOICE_ALIAS.get(parts[1], "体")
                           if len(parts) > 1 else "体"))
                i += 2
                continue
            errors.append(f"结 {nid} 缺词根")
            i += 1
            continue
        errors.append(f"无法解析的记号：{t!r}")
        i += 1
    return g

def parse(text: str) -> Graph:
    """把一段洄文源文本解析成关系图（记号流，支持子图嵌套与一行多句）。"""
    errors: list[str] = []
    g = _parse_tokens(_tokenize(text), errors)
    g.source_text = text
    # 把端点从「记号」还原成结对象：此处补一次存在性检查
    for r in g.rels:
        for side in ("src", "dst"):
            v = getattr(r, side)
            if v is not None and v not in g.nodes:
                errors.append(f"弓指向未声明的结：{v!r}")
                setattr(r, side, None)
    # 默认槽序（用于回填未指定位的临弓）
    cnt: dict[str, int] = {}
    for r in g.rels:
        if r.kind == "lin" and r.src:
            r.slot_order = cnt.get(r.src, 0)
            cnt[r.src] = r.slot_order + 1
    g.parse_errors = errors       # type: ignore[attr-defined]
    return g


def fill_roles(g: Graph, lex: dict[str, dict]) -> None:
    """按槽表把未指定位的临弓回填成具体临位。"""
    per: dict[str, int] = {}
    for r in g.rels:
        if r.kind != "lin" or r.src is None:
            continue
        k = per.get(r.src, 0)
        if not r.role:
            slots = slots_of(lex, g.nodes[r.src].root)
            r.role = slots[k] if k < len(slots) else "乙"
        per[r.src] = k + 1


def _join_brackets(text: str) -> str:
    """把跨行的方括号（子图）折成一行。方括号在洄文里只用于子图端点，
    因此这个折叠不会改变语义，只是把「写在几行上」变成「写在一行上」。"""
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        if depth == 0 and not line.startswith("["):
            out.append(raw)
            continue
        if depth == 0:
            buf = []
        if line:
            buf.append(line)
        depth += line.count("[") - line.count("]")
        if depth <= 0:
            out.append(" ".join(buf))
            buf, depth = [], 0
    if buf:
        out.append(" ".join(buf))
    return "\n".join(out)


def parse_document(text: str) -> list[Graph]:
    """一个文件可含多张图，用 `.graph <标题>` 分隔。无该指令时整个文件算一张图。"""
    text = _join_brackets(text)
    chunks: list[tuple[str, list[str]]] = []
    cur_title: str = ""
    cur: list[str] = []
    for raw in text.splitlines():
        s = raw.split("//")[0].strip()
        if s.startswith(".graph"):
            if any(x.split("//")[0].strip() for x in cur):
                chunks.append((cur_title, cur))
            cur_title, cur = s[6:].strip(), []
            continue
        cur.append(raw)
    if any(x.split("//")[0].strip() for x in cur):
        chunks.append((cur_title, cur))
    out = []
    for title, lines in chunks:
        body = "\n".join(lines)
        if not body.strip():
            continue          # `.graph` 之前的前言或空块，跳过
        g = parse(body)
        g.title = title
        link_subgraphs(g)
        out.append(g)
    return out or [parse(text)]


# ---------------------------------------------------------------- 校验
def validate(g: Graph, lex: dict[str, dict]) -> list[str]:
    errs: list[str] = list(getattr(g, "parse_errors", []))
    if not g.nodes:
        errs.append("空图")
        return errs

    # 律1 结必有根
    for nid in g.order:
        n = g.nodes[nid]
        if not n.is_ref and not n.root:
            errs.append(f"结 {nid} 没有词根")
        if n.root and lex and n.root not in lex:
            errs.append(f"结 {nid} 的词根 {n.root!r} 不在词表里")

    # 律2 弓必双向
    for r in g.rels:
        if r.src is None and r.src_sub is None:
            errs.append(f"{r.kind} 弓缺起点")
        if r.dst is None and r.dst_sub is None:
            errs.append(f"{r.kind} 弓缺终点")
    # 律3 临位必满（子图作端点时，子图整体算填了一个槽）
    for nid in g.order:
        n = g.nodes[nid]
        if n.is_ref:
            continue
        need = slots_of(lex, n.root)
        own = [r for r in g.rels if r.kind == "lin"
               and (r.src == nid or (r.dst == nid and r.src is None and r.src_sub))]
        got = [r.role for r in g.rels
               if r.kind == "lin" and (r.src == nid or r.dst == nid)]
        if n.voice in ("用", "度") and len(own) < len(need):
            miss = [s for s in need if s not in got]
            errs.append(f"临位未满：结 {nid}（{n.root}）槽表 {''.join(need)}，"
                        f"实填 {''.join(got) or '无'}，缺 {''.join(miss) or '—'}")

    # 律5 禁环：无向连通（子图内部自成一张图，故只在本图的结上判）
    main = g.flat()
    edge: dict[str, set[str]] = {nid: set() for nid in main.order}
    for r in main.rels:
        left = [r.src] if r.src else (r.src_sub.order if r.src_sub else [])
        right = [r.dst] if r.dst else (r.dst_sub.order if r.dst_sub else [])
        for a in left:
            for b in right:
                if a in edge and b in edge:
                    edge[a].add(b)
                    edge[b].add(a)
    seen: set[str] = set()
    stack = [main.order[0]] if main.order else []
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(edge[cur] - seen)
    orphans = [nid for nid in main.order if nid not in seen]
    if orphans:
        errs.append(f"不连通：结 {', '.join(orphans)} 接不到主结上")

    # 律6 义标必具
    if not g.evidence:
        errs.append("缺义标（§6 义标必具）：陈述句须标信息来源")

    # 律7 模态唯一（解析阶段只留一个，故只在有多载时报警——此处从略）
    return errs


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    lex = load_lexicon(here.parent / "lexicon.tsv")
    demo = """// 「我看见雨落在地上，在夜里」——义标：亲见
@0 yy4.体
@1 pe2.用
@2 po4.体
@3 ye4.体
@1 -> 0
@1 -戊-> 2
@1 -己-> 3
#see
"""
    g = parse(demo)
    attach(g, lex)
    fill_roles(g, lex)
    print(f"结 {len(g.nodes)}｜弓 {len(g.rels)}｜模态 {g.modal or '—'}｜义标 {g.evidence or '—'}")
    for nid in g.order:
        n = g.nodes[nid]
        print(f"  @{nid} {n.root}.{n.voice}  →  {n.syll or '?'} {n.zh or '?'}  #{n.index}")
    for r in g.rels:
        print(f"  {r.kind:3s} {r.src or '[子图]'} -{r.role or r.mark}- {r.dst or '[子图]'}")
    errs = validate(g, lex)
    print("校验:", "通过" if not errs else f"{len(errs)} 项")
    for e in errs:
        print("  -", e)
    raise SystemExit(1 if errs else 0)
