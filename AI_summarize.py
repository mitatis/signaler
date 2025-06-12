#!/usr/bin/env python3
"""
批量翻译 Markdown + 摘要 + description

1. 递归遍历 SRC_DIR 下所有 *.md
2. 将正文翻译为简体中文
3. 生成摘要（默认 < 200 字）并放在 front-matter 后
4. 生成一句话介绍写入 front-matter.description
5. 在 DST_DIR 下按原相对路径写入新文件；DST_DIR 可已存在；不存在时自动创建；同名文件将被覆盖
6. 处理完成的源文件将被重命名，文件名前加 “[ds]”；再次运行脚本时会自动跳过已标记文件
"""

from datetime import datetime as dt

from pathlib import Path
from openai import OpenAI
import yaml
import os
import sys
import re
import traceback

# ---------- 令牌计数工具 ----------
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def _token_len(txt: str) -> int:
        return len(_enc.encode(txt))
except ImportError:
    _enc = None
    def _token_len(txt: str) -> int:
        return len(txt)  # 后备：按字符近似

# ------------------------- 可按需修改的参数 -------------------------
SRC_DIR = Path("raw_" + dt.now().strftime("%Y-%m-%d"))   # 源目录
DST_DIR = Path("translated_" + dt.now().strftime("%Y-%m-%d"))   # 目标目录（需全新），位于当前项目中
MODEL   = "deepseek-chat"           # 或 deepseek-reasoner
BASE_URL = "https://api.deepseek.com"
KEY = ""
# -------------------------------------------------------------------
SUMMARY_CHARS = 200                 # 摘要字数上限
CHUNK_TOKENS = 8000          # 每块最大 token
CHUNK_OVERLAP = 200          # 邻接块重叠 token，保持语义
# -------------------------------------------------------------------

# 初始化 DeepSeek（OpenAI 兼容）客户端
client = OpenAI(
    api_key=KEY,
    base_url=BASE_URL
)

def ask_llm(prompt: str, temp: float = 1.0) -> str:
    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        stream=False
    )
    return res.choices[0].message.content.strip()

def split_front_matter(text: str):
    """拆分 front-matter(--- 包围) 与其余内容；若无 front-matter 返回空 dict"""
    if text.startswith('---\n'):
        end = text.find('\n---', 4)
        if end != -1:
            fm = text[4:end]
            body = text[end+4:].lstrip('\n')
            return yaml.safe_load(fm) or {}, body
    return {}, text


# ---------- Markdown 分块 ----------
_HDR_RE = re.compile(r'(?m)^#{1,6}\s')   # 标题行
def _split_markdown(md: str):
    """先按标题，再按 token 尺寸切片"""
    sections, buf = [], []
    for ln in md.splitlines(keepends=True):
        if _HDR_RE.match(ln) and buf:
            sections.append(''.join(buf))
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        sections.append(''.join(buf))

    out = []
    for seg in sections:
        if _token_len(seg) <= CHUNK_TOKENS:
            out.append(seg)
        else:
            if _enc:  # token 精确切
                toks = _enc.encode(seg)
                for i in range(0, len(toks), CHUNK_TOKENS - CHUNK_OVERLAP):
                    out.append(_enc.decode(toks[i:i+CHUNK_TOKENS]))
            else:     # 字符近似切
                step = (CHUNK_TOKENS - CHUNK_OVERLAP) * 4
                for i in range(0, len(seg), step):
                    out.append(seg[i:i+step])
    return out

def compose_markdown(front: dict, link: str, summary: str, body: str) -> str:
    fm_txt = yaml.safe_dump(front, allow_unicode=True, sort_keys=False).strip()
    link_block = f"*[源信息]({link})经过deepseek翻译并总结*\n\n" if link else ""
    summary_block = f"## 摘要：\n\n{summary}\n\n---\n\n"
    return f"---\n{fm_txt}\n---\n\n{link_block}{summary_block}{body}"

def process_one(src_path: Path, rel_root: Path, dst_root: Path):
    dst_path = dst_root / src_path.relative_to(rel_root)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    raw = src_path.read_text(encoding="utf-8")
    front, body = split_front_matter(raw)


    # 1) 译 front‑matter 中的标题（若存在）
    if "title" in front:
        front["title"] = ask_llm(f"请将以下标题翻译为简体中文，请不要添加任何除正文外的其它内容或者是AI翻译作为第三方的注解或评述，只保留翻译后的标题中文：\n{front['title']}", 1.3)

    # 将 front‑matter 中的 date 字段改名为 pubDatetime，并尽量转为 YAML timestamp
    if "date" in front:
        raw_date = front.pop("date")
        pub_dt = raw_date  # 默认保留原字符串
        if isinstance(raw_date, str):
            try:
                # 支持 ISO 日期或日期时间，自动识别 Z → +00:00
                pub_dt = dt.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        pub_dt = dt.strptime(raw_date, fmt)
                        break
                    except ValueError:
                        continue
        front["pubDatetime"] = pub_dt

    # 2) 分块 → 翻译
    segs = _split_markdown(body)
    translated_segs = [
        ask_llm(f"请将以下 Markdown 内容翻译为简体中文，保留原文中所有的有效正文并去除不相干的商业广告部分，保留所有原始超链接位置，保留 Markdown 语法但不添加任何代码块前后缀，不要添加任何额外内容：\n\n{seg}\n", 1.3)
        for seg in segs
    ]
    cn_body = "".join(translated_segs)

    # 3) 层级摘要
    lvl1 = [
        ask_llm(f"请用不超过 {2*SUMMARY_CHARS} 字总结以下段落，不要添加任何额外内容：\n\n{seg}", 1.0)
        for seg in translated_segs
    ]
    summary = ask_llm(
        f"以下是多段摘要，请综合压缩为不超过 {SUMMARY_CHARS} 字，不要添加任何额外内容：\n\n" + "\n".join(lvl1),
        1.0
    )

    # 4) 关键词提取并写入 tags
    keywords_resp = ask_llm(
        f"请从以下摘要中提取 2‑6 个用于检索的相关tags，保证清晰简洁明确。仅返回逗号、顿号或换行分隔的关键词列表，不要添加任何额外内容：\n\n{summary}"+"\n".join(lvl1),
        1.0
    )
    tags = [kw.strip() for kw in re.split(r"[,，、\n]+", keywords_resp) if kw.strip()]
    if tags:
        front["tags"] = tags

    # 5) 一句话介绍 (description)
    description = ask_llm(
        f"基于以下最终摘要，用一句话（≤50字）写一个简介：\n\n{summary}",
        1.0
    )
    front["description"] = description

    # 6) 重组并写入
    link = front.pop("link", None)  # 在写回前删除 link
    dst_path.write_text(
        compose_markdown(front, link, summary, cn_body),
        encoding="utf-8"
    )
    print(f"✔ {src_path} → {dst_path}")

def main():
    # 若目标目录不存在则创建；已存在则继续使用
    DST_DIR.mkdir(parents=True, exist_ok=True)

    # 收集未处理过的 Markdown 文件（跳过已 [ds] 前缀）
    md_files = [p for p in SRC_DIR.rglob("*.md") if not p.name.startswith("[ds]")]
    total = len(md_files)
    success = fail = 0

    for md in md_files:
        try:
            process_one(md, SRC_DIR, DST_DIR)
            success += 1
            # 给源文件加前缀 [ds]，表示已处理
            ds_path = md.with_name(f"[ds]{md.name}")
            if ds_path.exists():
                ds_path.unlink()
            md.rename(ds_path)
        except Exception as e:
            fail += 1
            print(f"[失败] {md} → {e}")
            traceback.print_exc()
    
    # 总结
    print(f"处理完成：共 {total} 篇，成功 {success} 篇，失败 {fail} 篇")

if __name__ == "__main__":
    main()