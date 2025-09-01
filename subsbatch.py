#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch subtitle sync with ffsubsync (GUI folder picker, terminal-only messages).

Changes from your original:
- Output .srt is named after the MATCHED VIDEO file (e.g., video.mp4 -> video.srt)
- No tkinter messageboxes; all status/summaries are printed to the terminal
"""

import sys
import subprocess
from pathlib import Path
from difflib import SequenceMatcher
import tkinter as tk
from tkinter import filedialog

# ---------------------- BEHAVIOR (tweak as you like) ---------------------- #
RECURSIVE = False        # set True to scan subfolders
OVERWRITE = False        # set True to overwrite existing output .srt
THRESHOLD = 0.55         # minimal similarity (0..1) to accept a match
MEDIA_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".mpg", ".mpeg",
    ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg"
}
SUB_EXTS = {".srt"}      # ffsubsync works best with .srt
# -------------------------------------------------------------------------- #

def have(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def run(cmd):
    print("→", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def best_media_match(for_sub: Path, media_files: list[Path]) -> Path | None:
    """Pick the media whose name is most similar to the subtitle filename (stem)."""
    s = normalize_stem(for_sub.stem)
    best = None
    best_score = -1.0
    for m in media_files:
        ms = normalize_stem(m.stem)
        ratio = SequenceMatcher(None, s, ms).ratio()
        length_bias = 1.0 - (abs(len(s) - len(ms)) / max(len(s), len(ms), 1)) * 0.1
        score = ratio * length_bias
        if score > best_score:
            best_score = score
            best = m
    return best if best and best_score >= THRESHOLD else None

def normalize_stem(stem: str) -> str:
    t = stem.lower()
    for ch in ["_", ".", "-", "(", ")", "[", "]"]:
        t = t.replace(ch, " ")
    return " ".join(t.split()).strip()

def gather_files(root: Path) -> list[Path]:
    if RECURSIVE:
        return [p for p in root.rglob("*") if p.is_file()]
    else:
        return [p for p in root.glob("*") if p.is_file()]

def main():
    if not have("ffsubsync"):
        print("❌ ffsubsync not found.\n   Install with either:\n   pip install ffsubsync\n   # or\n   conda install -c conda-forge ffsubsync")
        sys.exit(1)

    # GUI folder picker
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Pick the folder with your videos and subtitles")
    if not folder:
        print("❌ Cancelled: no folder selected.")
        sys.exit(0)
    base = Path(folder)

    all_files = gather_files(base)
    subs = [p for p in all_files if p.suffix.lower() in SUB_EXTS]

    # Group media by directory for local matching with each .srt
    media_by_dir: dict[Path, list[Path]] = {}
    for p in all_files:
        if p.suffix.lower() in MEDIA_EXTS:
            media_by_dir.setdefault(p.parent, []).append(p)

    if not subs:
        print("ℹ️  No .srt files found in the selected location.")
        sys.exit(0)

    synced: list[tuple[Path, Path]] = []
    skipped: list[tuple[Path, str]] = []
    failed: list[tuple[Path, str]] = []

    for srt in subs:
        candidates = media_by_dir.get(srt.parent, [])
        if not candidates:
            print(f"⚠️  No media in same folder as: {srt.name}")
            failed.append((srt, "no media in folder"))
            continue

        m = best_media_match(srt, candidates)
        if not m:
            print(f"⚠️  Could not find a good match for: {srt.name}")
            failed.append((srt, "no good match"))
            continue

        # Output name follows the VIDEO's base name, in the video's directory:
        out_srt = m.with_suffix(".srt")   # use ".synced.srt" if you prefer

        if out_srt.exists() and not OVERWRITE:
            print(f"⏩ Skip (exists): {out_srt.name}  [matched: {m.name}]")
            skipped.append((srt, "exists"))
            continue

        print(f"\n🎯 {srt.name}\n    ↳ matched media: {m.name}\n    ↳ output: {out_srt.name}")

        cmd = ["ffsubsync", str(m), "-i", str(srt), "-o", str(out_srt)]
        code, out, err = run(cmd)
        if code == 0:
            if out.strip():
                print(out)
            if err.strip():
                print(err)
            print(f"✅ Wrote: {out_srt}")
            synced.append((srt, m))
        else:
            print(f"❌ ffsubsync failed for: {srt}\n{err}")
            failed.append((srt, f"ffsubsync error ({code})"))

    # Terminal summary (no dialogs)
    print("\n=== SUMMARY ===")
    print(f"Synced : {len(synced)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Failed : {len(failed)}\n")

    if synced:
        print("[OK]")
        for srt, media in synced:
            print(f"  {srt.name}  ->  {media.stem}.srt")
    if skipped:
        print("\n[SKIP]")
        for srt, reason in skipped:
            print(f"  {srt.name}  ({reason})")
    if failed:
        print("\n[FAIL]")
        for srt, reason in failed:
            print(f"  {srt.name}  ({reason})")

if __name__ == "__main__":
    # Initialize (and hide) Tk so the file dialog works cleanly
    try:
        tk.Tk().destroy()
    except Exception:
        pass
    main()

