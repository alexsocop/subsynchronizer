#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

def have(cmd: str) -> bool:
    from shutil import which
    return which(cmd) is not None

def run(cmd, env=None):
    print("→", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    return p.returncode, p.stdout, p.stderr

def pick_media_and_subs():
    root = tk.Tk()
    root.withdraw()

    media = filedialog.askopenfilename(
        title="Select Video/Audio File",
        filetypes=[
            ("Media", "*.mp4 *.mkv *.mov *.avi *.mp3 *.m4a *.aac *.flac *.wav *.ogg"),
            ("All files", "*.*"),
        ],
    )
    if not media:
        print("❌ Cancelled: no media selected.")
        sys.exit(0)

    subs = filedialog.askopenfilename(
        title="Select Subtitle File (.srt preferred)",
        filetypes=[("SubRip Subtitles", "*.srt"), ("All files", "*.*")],
    )
    if not subs:
        print("❌ Cancelled: no subtitle selected.")
        sys.exit(0)

    return Path(media), Path(subs)

def align_with_ffsubsync(media: Path, subs: Path, out_srt: Path):
    cmd = ["ffsubsync", str(media), "-i", str(subs), "-o", str(out_srt)]
    code, out, err = run(cmd)
    if code != 0:
        raise RuntimeError(f"ffsubsync failed.\n--- STDOUT ---\n{out}\n--- STDERR ---\n{err}")
    if out.strip():
        print(out)
    if err.strip():
        print(err)

def maybe_align_with_aeneas(media: Path, subs: Path, out_srt: Path):
    import tempfile, re

    def srt_to_plaintext(srt_path: Path, out_txt: Path) -> Path:
        patt_ts = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}$")
        lines = []
        with srt_path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.isdigit() or patt_ts.match(line):
                    continue
                line = re.sub(r"</?[^>]+>", "", line)
                line = re.sub(r"\{\\.*?\}", "", line)
                lines.append(line)
        with out_txt.open("w", encoding="utf-8") as g:
            g.write("\n".join(lines) + "\n")
        return out_txt

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        text = srt_to_plaintext(subs, td / "text.txt")

        if not have("ffmpeg") or not have("ffprobe"):
            raise RuntimeError("aeneas fallback needs ffmpeg/ffprobe in PATH.")
        wav = td / "audio.wav"
        cmd = [
            "ffmpeg", "-hide_banner", "-nostdin", "-y",
            "-i", str(media),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-map_metadata", "-1", "-fflags", "+bitexact", "-flags", "+bitexact",
            "-f", "wav", str(wav)
        ]
        code, out, err = run(cmd)
        if code != 0:
            raise RuntimeError(f"FFmpeg failed to prepare WAV.\n{err}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "UTF-8"
        config = "task_language=eng|is_text_type=plain|os_task_file_format=srt"
        rconf = "ffmpeg_sample_rate=16000"
        cmd = [
            sys.executable, "-m", "aeneas.tools.execute_task", "-v",
            str(wav), str(text), config, str(out_srt), "-r", rconf
        ]
        code, out, err = run(cmd, env=env)
        if code != 0:
            raise RuntimeError(
                "aeneas failed even in fallback path.\n--- STDOUT ---\n"
                + out + "\n--- STDERR ---\n" + err
            )

def main():
    media, subs = pick_media_and_subs()

    # Output filename based on the VIDEO name
    out_srt = media.with_suffix(".srt")

    if have("ffsubsync"):
        try:
            align_with_ffsubsync(media, subs, out_srt)
            print(f"\n✅ Done! Synced subtitles written to: {out_srt}")
            return
        except Exception as e:
            print(f"⚠️ ffsubsync failed: {e}\nTrying aeneas fallback…")
    else:
        print("⚠️ ffsubsync not found. Install it with:\n   pip install ffsubsync\nTrying aeneas fallback…")

    try:
        import aeneas  # noqa: F401
        maybe_align_with_aeneas(media, subs, out_srt)
        print(f"\n✅ Done (aeneas)! Synced subtitles written to: {out_srt}")
    except ImportError:
        print("❌ Neither ffsubsync nor aeneas available.\n"
              "Please install ffsubsync with:\n   pip install ffsubsync")
    except Exception as e:
        print(f"❌ aeneas fallback failed: {e}")

if __name__ == "__main__":
    main()

