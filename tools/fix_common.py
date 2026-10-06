#!/usr/bin/env python3
"""
fix_common.py — ASR 修复脚本公共模块

所有 fix_epNNN.py 只需导入此模块并定义 REPLACEMENTS 和 CONTEXT_REPLACEMENTS。

REPLACEMENTS = {错误写法: 正确写法}
CONTEXT_REPLACEMENTS = [(正则模式, 替换), ...]

`apply_replacements` 幂等：重复运行不会二次替换。
"""
import re
from pathlib import Path


def parse_blocks(text):
    """返回块列表，每个块是 [序号, 时间码, 文本]。非标准块原样保留。"""
    blocks = []
    for chunk in text.strip().split("\n\n"):
        lines = chunk.split("\n")
        if len(lines) >= 2 and "-->" in lines[1]:
            num = lines[0]
            tc = lines[1]
            body = "\n".join(lines[2:])
            blocks.append([num, tc, body])
        else:
            blocks.append([None, None, chunk])
    return blocks


def apply_replacements(blocks, replacements):
    """在块列表上应用替换，自动处理被块边界切断的词。幂等。

    分两步：
    1. 块内替换：对每个块的文本做字符串替换（等价于全局替换）
    2. 跨块替换：检查相邻块的拼接处是否有被切断的 wrong，
       若有，找到 wrong 和 right 的公共前缀，只替换不同的部分：
       - 若 wrong[:split] == right[:split]（公共前缀在前块），只改后块
       - 否则把 right 拆分：前块放 right[:split]，后块放 right[split:]
    """
    total = 0
    # 1. 块内替换
    for b in blocks:
        if b[2] is None:
            continue
        for wrong, right in replacements.items():
            if wrong == right:
                continue
            count = b[2].count(wrong)
            if count:
                b[2] = b[2].replace(wrong, right)
                total += count

    # 2. 跨块替换
    for wrong, right in replacements.items():
        if wrong == right:
            continue
        for i in range(len(blocks) - 1):
            a, c = blocks[i], blocks[i + 1]
            if a[2] is None or c[2] is None:
                continue
            junction = a[2] + c[2]
            if wrong not in junction:
                continue
            # 只处理确实跨越边界的出现
            found = False
            for m in re.finditer(re.escape(wrong), junction):
                s, e = m.start(), m.end()
                if s < len(a[2]) < e:  # 跨越边界
                    found = True
                    break
            if not found:
                continue
            # 公共前缀
            split = 0
            while split < min(len(wrong), len(right)) and wrong[split] == right[split]:
                split += 1
            if wrong[:split] == right[:split] and split >= len(a[2]) - 0 and split > 0 and split <= len(a[2]):
                # 公共前缀落在前块内，只需改后块
                c[2] = right[split:] + c[2][len(wrong) - split:]
                total += 1
            else:
                head = right[:split]
                tail = right[split:]
                a[2] = head + a[2][: len(a[2]) - split] if split else a[2]
                c[2] = tail + c[2][len(wrong) - split:]
                total += 1
    return total


def run(srt_path, replacements, context_replacements=None):
    """执行修复流程。

    Args:
        srt_path: SRT 文件路径（相对或绝对）
        replacements: REPLACEMENTS 字典 {错误: 正确}
        context_replacements: CONTEXT_REPLACEMENTS 列表 [(模式, 替换)]

    Returns:
        修正总数
    """
    path = Path(srt_path)
    text = path.read_text(encoding="utf-8")
    total = 0
    blocks = parse_blocks(text)
    total += apply_replacements(blocks, replacements)

    out_parts = []
    for b in blocks:
        if b[0] is None:
            out_parts.append(b[2])
        else:
            out_parts.append(f"{b[0]}\n{b[1]}\n{b[2]}")
    text = "\n\n".join(out_parts) + "\n"

    for pattern, replacement in (context_replacements or []):
        new_text, count = re.subn(pattern, replacement, text)
        if count:
            text = new_text
            total += count
            print(f"  (regex) {pattern} → {replacement}  ×{count}")

    path.write_text(text, encoding="utf-8")
    print(f"{path.name}: 共修正 {total} 处")
    return total
