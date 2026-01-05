#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vtt_toolkit.py — All-in-one CLI for VTT subtitles:

Includes 4 functions (your 4 scripts) in ONE file:
1) Clean / check / fix timeline (timestamps)
2) Split VTT into N-minute parts
3) Merge VTT parts back into one file (chronological)
4) Compress cues (merge adjacent short cues into more integrated sentences)

It also provides 2 convenience combos:
- cleansplit (clean+fix -> split)
- mergecompress (merge -> compress)

Examples (Windows PowerShell):
  python vtt_toolkit.py clean --in "input.vtt" --fix
  python vtt_toolkit.py split --in "input_fixed.vtt" --out_dir "parts" --minutes 10
  python vtt_toolkit.py merge --parts_dir "parts" --pattern "*english.vtt" --out "merged_english.vtt"
  python vtt_toolkit.py compress --in "merged_english.vtt" --out "merged_english_compressed.vtt"

  python vtt_toolkit.py cleansplit --in "input.vtt" --out_dir "parts" --minutes 10
  python vtt_toolkit.py mergecompress --parts_dir "parts" --pattern "*english.vtt" --out "merged_english_compressed.vtt"

Notes:
- This does NOT translate. Translation can be done between split and merge (e.g., via QCLI).
- Timestamp parsing is robust and tolerates non-standard formats like "46.550" or dirty "55:56.03.800".
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


# ----------------------------
# Core regex + timestamp utils
# ----------------------------

TS_LINE_RE = re.compile(r"^\s*(.+?)\s*-->\s*(.+?)(\s+.*)?$")

def parse_ts_to_ms(ts: str) -> int:
    """
    Parse timestamps into milliseconds.

    Accepts:
      - HH:MM:SS.mmm
      - MM:SS.mmm
      - SS.mmm   (non-standard)
    Tolerates dirty formats like "55:56.03.800" (multiple dots) by extracting digits.
    Also accepts comma decimals (46,550).
    """
    ts = ts.strip().replace(",", ".")
    if not ts:
        raise ValueError("empty timestamp")

    # Pure seconds: "46.550"
    if re.fullmatch(r"\d+(\.\d+)?", ts):
        return int(float(ts) * 1000)

    parts = ts.split(":")
    if len(parts) == 3:
        hh, mm, rest = parts
    elif len(parts) == 2:
        hh = "0"
        mm, rest = parts
    else:
        raise ValueError(f"bad timestamp structure: {ts}")

    # rest may be "56.800" or dirty "56.03.800"
    rest_parts = rest.split(".")
    ss = rest_parts[0] if rest_parts[0] else "0"

    # ms digits = concat everything after the first dot, then keep digits only
    ms_digits = "".join(rest_parts[1:]) if len(rest_parts) > 1 else "0"
    ms_digits = re.sub(r"\D", "", ms_digits)
    if ms_digits == "":
        ms_digits = "0"
    mmm = int(ms_digits.ljust(3, "0")[:3])

    return (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000 + mmm


def ms_to_vtt(ms: int) -> str:
    """Format ms as WEBVTT timestamp HH:MM:SS.mmm"""
    if ms < 0:
        ms = 0
    hh = ms // 3600_000
    ms %= 3600_000
    mm = ms // 60_000
    ms %= 60_000
    ss = ms // 1000
    mmm = ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{mmm:03d}"


# ----------------------------
# IO helpers
# ----------------------------

def read_text_lines(path: Path) -> List[str]:
    # utf-8-sig handles BOM if present
    txt = path.read_text(encoding="utf-8-sig", errors="replace")
    return txt.replace("\r\n", "\n").replace("\r", "\n").splitlines(True)  # keep line endings


def write_text_lines(path: Path, lines: List[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def split_header_and_body(lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    WEBVTT header = "WEBVTT" line + optional metadata until first blank line.
    Body = everything after that blank line.
    """
    i = 0
    # skip leading blanks
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    header: List[str] = []
    if i < len(lines) and lines[i].lstrip("\ufeff").strip().upper().startswith("WEBVTT"):
        header.append(lines[i].lstrip("\ufeff"))
        i += 1

    # optional header metadata until blank line
    while i < len(lines) and lines[i].strip() != "":
        header.append(lines[i])
        i += 1

    # include exactly one blank line separator if present
    while i < len(lines) and lines[i].strip() == "":
        header.append(lines[i])
        i += 1
        # keep only first blank line(s) in header to separate, but harmless to keep all

    body = lines[i:]
    return header, body


# ----------------------------
# 1) CLEAN / CHECK / FIX
# ----------------------------

def check_and_collect_issues(lines: List[str]):
    issues = []
    cues = []  # (line_no, start_ms, end_ms, raw_line)

    for idx, line in enumerate(lines, start=1):
        m = TS_LINE_RE.match(line)
        if not m:
            continue

        start_raw = m.group(1).strip()
        end_raw_full = m.group(2).strip()
        end_raw = end_raw_full.split()[0]  # drop settings if stuck here
        raw_line = line.rstrip("\n")

        try:
            s_ms = parse_ts_to_ms(start_raw)
            e_ms = parse_ts_to_ms(end_raw)
        except Exception as e:
            issues.append((idx, "PARSE_FAIL", str(e), raw_line))
            continue

        if e_ms < s_ms:
            issues.append((idx, "END_BEFORE_START", f"start={s_ms} end={e_ms}", raw_line))

        cues.append((idx, s_ms, e_ms, raw_line))

    # Timeline sanity: start should be non-decreasing; cues shouldn't overlap
    last_start = None
    last_end = None
    last_line = None
    for (ln, s_ms, e_ms, raw_line) in cues:
        if last_start is not None:
            if s_ms < last_start:
                issues.append((ln, "START_DECREASED",
                               f"prev_start={last_start} current_start={s_ms} (prev line {last_line})",
                               raw_line))
            if last_end is not None and s_ms < last_end:
                issues.append((ln, "OVERLAP",
                               f"prev_end={last_end} current_start={s_ms} (prev line {last_line})",
                               raw_line))
        last_start, last_end, last_line = s_ms, e_ms, ln

    return issues, cues


def fix_vtt_timestamps(lines: List[str]):
    """
    Fix mode:
      - Rewrites each timestamp line to "HH:MM:SS.mmm --> HH:MM:SS.mmm" and preserves trailing settings.
      - If end < start, swaps them.
      - Leaves unparseable timestamp lines unchanged (but logs them).
    """
    fixed_lines: List[str] = []
    fix_log: List[Tuple[int, str, str]] = []  # (line_no, action, detail)

    for idx, line in enumerate(lines, start=1):
        m = TS_LINE_RE.match(line)
        if not m:
            fixed_lines.append(line)
            continue

        start_raw = m.group(1).strip()
        end_and_more = m.group(2).strip()
        tail = m.group(3) or ""  # includes leading spaces if present

        end_raw = end_and_more.split()[0]

        try:
            s_ms = parse_ts_to_ms(start_raw)
            e_ms = parse_ts_to_ms(end_raw)
        except Exception as e:
            fixed_lines.append(line)
            fix_log.append((idx, "SKIP_UNPARSEABLE", str(e)))
            continue

        swapped = False
        if e_ms < s_ms:
            s_ms, e_ms = e_ms, s_ms
            swapped = True

        new_line = f"{ms_to_vtt(s_ms)} --> {ms_to_vtt(e_ms)}{tail}".rstrip() + "\n"
        fixed_lines.append(new_line)

        if swapped:
            fix_log.append((idx, "SWAP_START_END", f"{start_raw} --> {end_raw}"))
        else:
            if line.strip() != new_line.strip():
                fix_log.append((idx, "NORMALIZE", f"{start_raw} --> {end_raw}"))

    return fixed_lines, fix_log


def cmd_clean(in_file: str, out_file: Optional[str], fix: bool, show: int) -> int:
    in_path = Path(in_file)
    lines = read_text_lines(in_path)

    issues, _ = check_and_collect_issues(lines)

    print(f"Checked: {in_path}")
    print(f"Issues found: {len(issues)}")
    for ln, kind, detail, raw in issues[:show]:
        print(f"[Line {ln}] {kind}: {detail}\n  {raw}")
    if len(issues) > show:
        print(f"... ({len(issues) - show} more)")

    if fix:
        fixed_lines, fix_log = fix_vtt_timestamps(lines)
        out_path = Path(out_file) if out_file else in_path.with_name(f"{in_path.stem}_fixed{in_path.suffix}")
        write_text_lines(out_path, fixed_lines)

        print("\n=== Fix mode ===")
        print(f"Wrote: {out_path}")
        print(f"Timestamp lines normalized/swapped/skipped: {len(fix_log)}")
        for ln, action, detail in fix_log[:show]:
            print(f"[Line {ln}] {action}: {detail}")
        if len(fix_log) > show:
            print(f"... ({len(fix_log) - show} more)")

    return 0


# ----------------------------
# 2) SPLIT
# ----------------------------

@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text_lines: List[str]
    ts_line: str

def iter_cues(body_lines: List[str]) -> List[Cue]:
    """
    Parse cue blocks from body lines while preserving original text lines.
    Returns Cue objects with parsed start/end times for splitting.
    """
    cues: List[Cue] = []
    i = 0
    while i < len(body_lines):
        line = body_lines[i]
        m = TS_LINE_RE.match(line)
        if not m:
            i += 1
            continue

        start_raw = m.group(1).strip()
        end_raw_full = m.group(2).strip()
        end_raw = end_raw_full.split()[0]
        ts_line = line.rstrip("\n")

        try:
            s_ms = parse_ts_to_ms(start_raw)
            e_ms = parse_ts_to_ms(end_raw)
        except Exception:
            # skip malformed cue
            i += 1
            continue

        i += 1
        txt: List[str] = []
        while i < len(body_lines) and body_lines[i].strip() != "":
            txt.append(body_lines[i].rstrip("\n"))
            i += 1

        # consume blank lines
        while i < len(body_lines) and body_lines[i].strip() == "":
            i += 1

        cues.append(Cue(start_ms=s_ms, end_ms=e_ms, text_lines=txt, ts_line=ts_line))

    return cues


def cmd_split(in_file: str, out_dir: Optional[str], minutes: int, rebase: bool, start_at_zero: bool) -> int:
    in_path = Path(in_file)
    lines = read_text_lines(in_path)
    header, body = split_header_and_body(lines)
    cues = iter_cues(body)

    if not cues:
        raise ValueError("No cues found. Is this a valid VTT with timestamp lines?")

    out_base_dir = Path(out_dir) if out_dir else in_path.parent
    out_base_dir.mkdir(parents=True, exist_ok=True)

    chunk_ms = minutes * 60_000

    # decide base timeline for chunking
    if start_at_zero:
        base_ms = 0
    else:
        base_ms = (min(c.start_ms for c in cues) // chunk_ms) * chunk_ms

    def chunk_index(start_ms: int) -> int:
        return max(0, int((start_ms - base_ms) // chunk_ms))

    # group cues
    buckets: List[List[Cue]] = []
    for c in cues:
        idx = chunk_index(c.start_ms)
        while len(buckets) <= idx:
            buckets.append([])
        buckets[idx].append(c)

    stem = in_path.stem
    written = 0

    for idx, bucket in enumerate(buckets, start=1):
        if not bucket:
            continue

        chunk_start = base_ms + (idx - 1) * chunk_ms

        out_lines: List[str] = []
        # header
        if header:
            out_lines.extend(header)
        else:
            out_lines.extend(["WEBVTT\n", "\n"])

        # cues
        for c in bucket:
            if rebase:
                # rewrite timestamp line to rebased HH:MM:SS.mmm values
                s = c.start_ms - chunk_start
                e = c.end_ms - chunk_start
                out_lines.append(f"{ms_to_vtt(s)} --> {ms_to_vtt(e)}\n")
            else:
                out_lines.append(c.ts_line.rstrip() + "\n")
            for t in c.text_lines:
                out_lines.append(t + "\n")
            out_lines.append("\n")

        out_path = out_base_dir / f"{stem}_part{idx}.vtt"
        write_text_lines(out_path, out_lines)
        written += 1

    print(f"Split wrote {written} file(s) -> {out_base_dir}")
    return 0


# ----------------------------
# 3) MERGE
# ----------------------------

# Match "part2", "_part02", "Part 10", etc. anywhere in the filename stem
PARTNUM_RE = re.compile(r"(?:^|[^a-zA-Z])_?part\s*0*(\d+)", re.IGNORECASE)

def part_number_from_name(path: Path) -> int:
    m = PARTNUM_RE.search(path.stem)
    if not m:
        return 10**9  # very large => sorts after real parts
    try:
        return int(m.group(1))
    except Exception:
        return 10**9

def first_cue_start_ms(path: Path) -> int:
    lines = read_text_lines(path)
    _, body = split_header_and_body(lines)
    for line in body:
        m = TS_LINE_RE.match(line)
        if not m:
            continue
        start_raw = m.group(1).strip()
        try:
            return parse_ts_to_ms(start_raw)
        except Exception:
            continue
    return 10**12  # huge if no cues

def read_vtt_keep_header(path: Path) -> Tuple[List[str], List[str]]:
    lines = read_text_lines(path)
    header, body = split_header_and_body(lines)
    # Make sure header has WEBVTT at least once
    if not header:
        header = ["WEBVTT\n", "\n"]
    return header, body

def cmd_merge(parts_dir: str, output_file: str, pattern: str) -> int:
    pdir = Path(parts_dir)
    files = [f for f in pdir.glob(pattern) if f.is_file()]
    if not files:
        raise FileNotFoundError(f"No VTT files found in: {parts_dir} (pattern={pattern})")

    enriched = []
    for f in files:
        t0 = first_cue_start_ms(f)
        pn = part_number_from_name(f)
        enriched.append((t0, pn, f.name.lower(), f))

    enriched.sort(key=lambda x: (x[0], x[1], x[2]))
    files_sorted = [x[3] for x in enriched]

    out_lines: List[str] = []
    header_written = False

    for f in files_sorted:
        header, body = read_vtt_keep_header(f)

        if not header_written:
            out_lines.extend(header)
            # ensure at least one blank line after header
            if out_lines and out_lines[-1].strip() != "":
                out_lines.append("\n")
            header_written = True

        # Trim leading blank lines from body
        while body and body[0].strip() == "":
            body.pop(0)
        # Trim trailing blank lines
        while body and body[-1].strip() == "":
            body.pop()

        if body:
            out_lines.extend(body)
            out_lines.append("\n")

    Path(output_file).write_text("".join(out_lines).rstrip() + "\n", encoding="utf-8")

    print("Merge order (sorted):")
    for f in files_sorted:
        print("  ", f.name)
    print(f"\nMerged {len(files_sorted)} files -> {output_file}")
    return 0


# ----------------------------
# 4) COMPRESS
# ----------------------------

PUNCT_END = set(list(".?!。？！…"))
TAG_RE = re.compile(r"<[^>]+>")  # remove <c>, <v>, <i> ... tags
MULTI_SPACE_RE = re.compile(r"\s+")

def clean_text(s: str) -> str:
    s = (s or "").strip()
    s = TAG_RE.sub("", s)
    s = MULTI_SPACE_RE.sub(" ", s)
    return s

def ends_sentence(s: str) -> bool:
    s = clean_text(s)
    if not s:
        return True
    return s[-1] in PUNCT_END

def cmd_compress(in_file: str, out_file: str, gap_ms: int, max_chars: int) -> int:
    in_path = Path(in_file)
    content = in_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # parse cues -> list of (start_ms, end_ms, start_ts, end_ts, text)
    cues: List[Tuple[int, int, str, str, str]] = []
    i = 0

    # skip possible BOM / WEBVTT header / metadata lines
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip("\ufeff").strip().upper().startswith("WEBVTT"):
        i += 1

    # skip header metadata until blank line
    while i < len(lines) and lines[i].strip() != "":
        i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        m = TS_LINE_RE.match(lines[i])
        if not m:
            i += 1
            continue

        start_raw = m.group(1).strip()
        end_raw_full = m.group(2).strip()
        end_raw = end_raw_full.split()[0]

        start_ms = parse_ts_to_ms(start_raw)
        end_ms = parse_ts_to_ms(end_raw)

        # normalize timestamps for output
        start_ts = ms_to_vtt(start_ms)
        end_ts = ms_to_vtt(end_ms)

        i += 1
        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip() != "":
            text_lines.append(lines[i].strip())
            i += 1

        txt = clean_text(" ".join(text_lines))
        cues.append((start_ms, end_ms, start_ts, end_ts, txt))

        while i < len(lines) and i < len(lines) and lines[i].strip() == "":
            i += 1

    if not cues:
        raise ValueError("No cues parsed for compression. Is the input a valid VTT?")

    # sort by timeline just in case
    cues.sort(key=lambda x: (x[0], x[1]))

    # merge adjacent cues by logic
    merged: List[Tuple[str, str, str]] = []
    cur_start_ms, cur_end_ms, cur_start_ts, cur_end_ts, buffer = cues[0]

    for start_ms, end_ms, s_ts, e_ts, txt in cues[1:]:
        gap = start_ms - cur_end_ms
        if gap <= gap_ms and not ends_sentence(buffer) and (len(buffer) + 1 + len(txt)) <= max_chars:
            buffer = clean_text(buffer + " " + txt)
            cur_end_ms = max(cur_end_ms, end_ms)
            cur_end_ts = ms_to_vtt(cur_end_ms)
        else:
            merged.append((cur_start_ts, cur_end_ts, buffer))
            cur_start_ms, cur_end_ms, cur_start_ts, cur_end_ts, buffer = start_ms, end_ms, s_ts, e_ts, txt

    merged.append((cur_start_ts, cur_end_ts, buffer))

    # write output vtt
    out_lines = ["WEBVTT", ""]
    for s_ts, e_ts, txt in merged:
        out_lines.append(f"{s_ts} --> {e_ts}")
        out_lines.append(txt)
        out_lines.append("")

    Path(out_file).write_text("\n".join(out_lines).strip() + "\n", encoding="utf-8")
    print(f"Compressed cues: {len(cues)} -> {len(merged)}   Output: {out_file}")
    return 0


# ----------------------------
# Convenience combos
# ----------------------------

def cmd_cleansplit(in_file: str, out_dir: str, minutes: int, rebase: bool, start_at_zero: bool) -> int:
    in_path = Path(in_file)
    lines = read_text_lines(in_path)

    fixed_lines, _ = fix_vtt_timestamps(lines)
    fixed_path = in_path.with_name(f"{in_path.stem}_fixed{in_path.suffix}")
    write_text_lines(fixed_path, fixed_lines)
    print(f"Clean+fix wrote: {fixed_path}")

    return cmd_split(str(fixed_path), out_dir=out_dir, minutes=minutes, rebase=rebase, start_at_zero=start_at_zero)


def cmd_mergecompress(parts_dir: str, pattern: str, out_file: str, gap_ms: int, max_chars: int) -> int:
    # Merge to a temp next to output
    out_path = Path(out_file)
    tmp_merged = out_path.with_name(out_path.stem + "_tmp_merged.vtt")

    cmd_merge(parts_dir=parts_dir, output_file=str(tmp_merged), pattern=pattern)
    cmd_compress(in_file=str(tmp_merged), out_file=str(out_path), gap_ms=gap_ms, max_chars=max_chars)

    # best-effort cleanup
    try:
        tmp_merged.unlink()
    except Exception:
        pass

    return 0
  
def cmd_cleancompresssplit(in_file: str, out_dir: str, minutes: int, gap_ms: int, max_chars: int, rebase: bool, start_at_zero: bool) -> int:
   
    in_path = Path(in_file)
    out_path = Path(out_dir)
    
    # Step 1: Clean and fix timestamps
    lines = read_text_lines(in_path)
    fixed_lines, _ = fix_vtt_timestamps(lines)
    
    fixed_path = in_path.with_name(f"{in_path.stem}_fixed{in_path.suffix}")
    write_text_lines(fixed_path, fixed_lines)
    print(f"Clean+fix wrote: {fixed_path}")
    
    # Step 2: Compress the fixed file
    compressed_path = in_path.with_name(f"{in_path.stem}_compressed{in_path.suffix}")
    cmd_compress(in_file=str(fixed_path), out_file=str(compressed_path), gap_ms=gap_ms, max_chars=max_chars)
    print(f"Compressed to: {compressed_path}")
    
    # Step 3: Split the compressed file
    result = cmd_split(str(compressed_path), out_dir=out_dir, minutes=minutes, rebase=rebase, start_at_zero=start_at_zero)
    
    # Best-effort cleanup of temp files
    try:
        fixed_path.unlink()
        compressed_path.unlink()
    except Exception:
        pass
    
    return result


# ----------------------------
# CLI
# ----------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vtt_toolkit.py", description="All-in-one VTT toolkit (clean/split/merge/compress)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_clean = sub.add_parser("clean", help="Check timestamps and optionally normalize/fix them.")
    p_clean.add_argument("--in", dest="in_file", required=True, help="Input .vtt")
    p_clean.add_argument("--out", dest="out_file", default=None, help="Output .vtt (only used with --fix). Default: *_fixed.vtt")
    p_clean.add_argument("--fix", action="store_true", help="Write normalized/fixed timestamp lines")
    p_clean.add_argument("--show", type=int, default=50, help="How many items to print (default 50)")

    p_split = sub.add_parser("split", help="Split a VTT into N-minute parts.")
    p_split.add_argument("--in", dest="in_file", required=True, help="Input .vtt")
    p_split.add_argument("--out_dir", default=None, help="Output directory (default: same folder as input)")
    p_split.add_argument("--minutes", type=int, default=10, help="Chunk size in minutes (default 10)")
    p_split.add_argument("--rebase", action="store_true", help="Rewrite each part's timestamps to start at 00:00")
    p_split.add_argument("--start_at_zero", action="store_true",
                         help="Chunking base starts at 00:00 instead of aligning to first cue time")

    p_merge = sub.add_parser("merge", help="Merge multiple VTT files into one, ordered chronologically.")
    p_merge.add_argument("--parts_dir", required=True, help="Directory containing VTT parts")
    p_merge.add_argument("--pattern", default="*.vtt", help='Glob pattern (default "*.vtt"). Example "*english.vtt"')
    p_merge.add_argument("--out", dest="out_file", required=True, help="Output merged .vtt path")

    p_compress = sub.add_parser("compress", help="Compress a VTT by merging adjacent cues into longer sentences.")
    p_compress.add_argument("--in", dest="in_file", required=True, help="Input .vtt")
    p_compress.add_argument("--out", dest="out_file", required=True, help="Output .vtt")
    p_compress.add_argument("--gap_ms", type=int, default=500, help="Merge if next cue starts within this gap (ms). Default 500")
    p_compress.add_argument("--max_chars", type=int, default=130, help="Max chars per merged cue. Default 130")

    p_cs = sub.add_parser("cleansplit", help="Convenience: clean+fix then split.")
    p_cs.add_argument("--in", dest="in_file", required=True, help="Input .vtt")
    p_cs.add_argument("--out_dir", required=True, help="Output directory for parts")
    p_cs.add_argument("--minutes", type=int, default=10, help="Chunk size in minutes (default 10)")
    p_cs.add_argument("--rebase", action="store_true", help="Rewrite each part's timestamps to start at 00:00")
    p_cs.add_argument("--start_at_zero", action="store_true",
                      help="Chunking base starts at 00:00 instead of aligning to first cue time")

    p_mc = sub.add_parser("mergecompress", help="Convenience: merge parts then compress the merged output.")
    p_mc.add_argument("--parts_dir", required=True, help="Directory containing VTT parts")
    p_mc.add_argument("--pattern", default="*.vtt", help='Glob pattern (default "*.vtt"). Example "*english.vtt"')
    p_mc.add_argument("--out", dest="out_file", required=True, help="Final output .vtt path (compressed)")
    p_mc.add_argument("--gap_ms", type=int, default=500, help="Compress: merge if gap <= this (ms). Default 500")
    p_mc.add_argument("--max_chars", type=int, default=130, help="Compress: max chars per merged cue. Default 130")

    p_ccs = sub.add_parser("cleancompresssplit", help="Convenience: clean+fix, compress, then split.")
    p_ccs.add_argument("--in", dest="in_file", required=True, help="Input .vtt")
    p_ccs.add_argument("--out_dir", required=True, help="Output directory for parts")
    p_ccs.add_argument("--minutes", type=int, default=10, help="Chunk size in minutes (default 10)")
    p_ccs.add_argument("--gap_ms", type=int, default=500, help="Compress: merge if gap <= this (ms). Default 500")
    p_ccs.add_argument("--max_chars", type=int, default=130, help="Compress: max chars per merged cue. Default 130")
    p_ccs.add_argument("--rebase", action="store_true", help="Rewrite each part's timestamps to start at 00:00")
    p_ccs.add_argument("--start_at_zero", action="store_true", help="Chunking base starts at 00:00 instead of aligning to first cue time")

    return ap


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()

    if args.cmd == "clean":
        return cmd_clean(args.in_file, args.out_file, args.fix, args.show)

    if args.cmd == "split":
        return cmd_split(args.in_file, args.out_dir, args.minutes, args.rebase, args.start_at_zero)

    if args.cmd == "merge":
        return cmd_merge(args.parts_dir, args.out_file, args.pattern)

    if args.cmd == "compress":
        return cmd_compress(args.in_file, args.out_file, args.gap_ms, args.max_chars)

    if args.cmd == "cleansplit":
        return cmd_cleansplit(args.in_file, args.out_dir, args.minutes, args.rebase, args.start_at_zero)

    if args.cmd == "mergecompress":
        return cmd_mergecompress(args.parts_dir, args.pattern, args.out_file, args.gap_ms, args.max_chars)

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
