#!/usr/bin/env python3
"""
Multimedia CLI tool based on FFmpeg.
Features: format conversion, audio extraction, video clipping.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────

VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".ts", ".mts", ".3gp", ".ogv",
}
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif",
    ".gif", ".avif", ".heic", ".ico",
}
AUDIO_EXTS = {
    ".mp3", ".aac", ".wav", ".flac", ".ogg", ".wma",
    ".m4a", ".opus", ".ac3", ".aiff",
}
ALL_MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS

FORMATS_SUPPORTED = sorted({
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "ts",
    "mp3", "aac", "wav", "flac", "ogg", "wma", "m4a", "opus", "ac3",
    "jpg", "jpeg", "png", "bmp", "webp", "tiff", "gif", "ico", "avif",
})

FORMAT_SUGGEST = {
    "video": ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "ts"],
    "audio": ["mp3", "aac", "wav", "flac", "ogg", "m4a", "opus"],
    "image": ["jpg", "png", "webp", "bmp", "gif", "tiff", "avif", "ico"],
}

# ── Go-back signal ────────────────────────────────────────────────

class Back(Exception):
    """Raised when user types 'b' to go back to the previous step."""


# ── FFmpeg detection ──────────────────────────────────────────────

def find_ffmpeg():
    """Return ffmpeg executable path, or None if not found."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    prog = os.environ.get("ProgramFiles", "C:\\Program Files")
    local = os.environ.get("LOCALAPPDATA", "")
    for d in [Path(prog, "FFmpeg", "bin"), Path(local, "ffmpeg", "bin"),
              Path("C:\\ffmpeg\\bin"), Path(".")]:
        p = d / "ffmpeg.exe"
        if p.exists():
            return str(p)
    return None


FFMPEG = find_ffmpeg()

# ── Terminal helpers ──────────────────────────────────────────────

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title):
    width = 50
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


def input_required(prompt, back_to=None):
    """Prompt until non-empty input.  b / back / 返回 to go back."""
    hint = f" (输入 b 返回{back_to})" if back_to else " (输入 b 返回上一步)"
    while True:
        val = input(f"  > {prompt}{hint}: ").strip()
        if val.lower() in ("b", "back", "返回", "上一步"):
            raise Back()
        if val:
            return val
        print("  ! 此项为必填，请重新输入。")


def input_optional(prompt, default="", back_to=None):
    hint = f" (输入 b 返回{back_to})" if back_to else " (输入 b 返回上一步)"
    val = input(f"  > {prompt}{hint}: ").strip()
    if val.lower() in ("b", "back", "返回", "上一步"):
        raise Back()
    return val if val else default


def confirm(prompt, back_to=None):
    """Yes / no.  b / back / 返回 to go back."""
    hint = f" (输入 b 返回{back_to})" if back_to else " (输入 b 返回上一步)"
    while True:
        ans = input(f"  > {prompt}{hint} (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        if ans in ("b", "back", "返回", "上一步"):
            raise Back()
        print("  ! 请输入 y 或 n。")


# ── Time helpers ──────────────────────────────────────────────────

def time_str_to_seconds(s):
    """Convert HH:MM:SS, MM:SS or plain-seconds string to float."""
    parts = s.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        pass
    raise ValueError(f"无法解析时间: {s}")


def format_timestamp(seconds):
    """Format seconds as HH:MM:SS.ss"""
    h = int(seconds / 3600)
    m = int((seconds % 3600) / 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


# ── File selection ────────────────────────────────────────────────

def select_file():
    """Guide user to input a file path.  Returns Path, or None = exit."""
    while True:
        print_header("\U0001f4c2 选取文件")
        print("  支持拖拽文件到此处，或手动输入路径。")
        print("  支持的媒体格式: 视频 / 音频 / 图片")
        print()
        print("  [b] 退出程序")
        print()
        try:
            path_str = input_required("请输入文件路径", "退出程序")
        except Back:
            return None

        path_str = path_str.strip('"\'')

        p = Path(path_str).expanduser().resolve()
        if not p.exists():
            print(f"\n  ✗ 文件不存在: {p}")
            try:
                if not confirm("重新输入"):
                    return None
            except Back:
                continue
            continue
        if not p.is_file():
            print(f"\n  ✗ 路径不是一个文件: {p}")
            try:
                if not confirm("重新输入"):
                    return None
            except Back:
                continue
            continue
        if p.suffix.lower() not in ALL_MEDIA_EXTS:
            print(f"\n  ⚠ 文件格式 ({p.suffix}) 不在常见媒体格式列表中。")
            try:
                if not confirm("仍要使用此文件"):
                    continue
            except Back:
                continue

        return p


# ── Operation selection ───────────────────────────────────────────

def select_operation(file_path: Path):
    """Show available operations for the file type, return (key, label)."""
    ext = file_path.suffix.lower()

    if ext in VIDEO_EXTS:
        opts = [
            ("1", "格式转换", "convert"),
            ("2", "提取音频", "extract_audio"),
            ("3", "视频剪辑", "clip_video"),
        ]
        tlabel = "视频"
    elif ext in IMAGE_EXTS:
        opts = [("1", "格式转换", "convert")]
        tlabel = "图片"
    elif ext in AUDIO_EXTS:
        opts = [
            ("1", "格式转换", "convert"),
            ("2", "音频剪辑", "clip_audio"),
        ]
        tlabel = "音频"
    else:
        opts = [("1", "格式转换", "convert")]
        tlabel = "媒体"

    print_header(f"\U0001f3ac 选择操作  ({tlabel}: {file_path.name})")
    for num, label, _ in opts:
        print(f"    [{num}] {label}")
    print()
    print("    [b] 返回重新选取文件")
    print()

    while True:
        choice = input("  > 请输入操作编号: ").strip().lower()
        if choice in ("b", "back", "返回", "上一步"):
            raise Back()
        for num, label, key in opts:
            if choice == num:
                return key, label
        print(f"  ! 无效选择，请输入 1-{len(opts)}，或输入 b 返回。")


# ── Time input ────────────────────────────────────────────────────

def parse_time(prompt, back_to=None):
    """Get a validated time string from user.  Raises Back on b."""
    while True:
        try:
            t = input_required(prompt, back_to)
        except Back:
            raise

        try:
            time_str_to_seconds(t)
            return t.strip()
        except ValueError:
            print("  ! 格式错误。支持: HH:MM:SS / MM:SS / 秒数 (如 1:30 或 90)")


def get_time_range(first_back=None, second_back=None):
    """Get (start_str, end_str) time strings from user."""
    print("\n  ── 时间范围选择 ──")
    print("  格式: 1:30 表示1分30秒, 0:05:30 表示5分30秒, 120 表示120秒\n")
    start = parse_time("起始时间", first_back)
    end = parse_time("结束时间", second_back)
    return start, end


# ── Output path ───────────────────────────────────────────────────

def get_output_path(input_file: Path, category: str, back_to=None):
    """Ask user for output filename, format, and directory.
       Returns (out_path, fmt)."""
    print_header("\U0001f4be 输出设置")

    fmts = FORMAT_SUGGEST.get(category, FORMAT_SUGGEST["video"])
    print(f"  推荐 {category} 格式: {', '.join(fmts)}")
    print(f"  完整支持: {', '.join(FORMATS_SUPPORTED)}")
    print()

    name = input_required("输出文件名 (不含扩展名)", back_to)
    fmt = input_required("输出格式 (如 mp4 / mp3 / jpg)", "文件名输入")
    fmt = fmt.lower().strip(".")

    if fmt not in FORMATS_SUPPORTED:
        print(f"  ⚠ 格式 '{fmt}' 可能不受支持，将直接使用。")

    default_dir = str(input_file.parent)
    out_dir = input_optional(f"输出目录 (默认: {default_dir})", default_dir, "输出格式")
    out_path = Path(out_dir).expanduser().resolve() / f"{name}.{fmt}"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.resolve() == input_file.resolve():
        print("  ⚠ 输出文件与输入文件路径相同！请修改文件名或目录。")
        raise Back()

    return out_path, fmt


# ── Progress bar ──────────────────────────────────────────────────

def _draw_progress_bar(current, total=None, final=False):
    """Draw an inline progress bar adapting to terminal width."""
    try:
        cols = shutil.get_terminal_size().columns
    except (ValueError, OSError):
        cols = 80
    bar_w = max(10, min(50, cols - 55))

    if final:
        bar = "█" * bar_w
        t = format_timestamp(total or current)
        print(f"\r    [{bar}] 100.0%  {t}", end="", flush=True)
        return

    if total and total > 0:
        pct = min(current / total * 100, 100)
        fill = int(bar_w * pct / 100)
        bar = "█" * fill + "░" * (bar_w - fill)
        t = f"{format_timestamp(current)} / {format_timestamp(total)}"
        print(f"\r    [{bar}] {pct:5.1f}%  {t}", end="", flush=True)
    else:
        print(f"\r    [{'░' * bar_w}] 处理中... {format_timestamp(current) if current else ''}",
              end="", flush=True)


# ── FFmpeg runner ─────────────────────────────────────────────────

def run_ffmpeg(args, description="", total_sec_hint=None, extra_args_preset=None):
    """
    Run ffmpeg with a real-time progress bar.

    Returns (success_bool, extra_args_used_or_None).

    extra_args_preset — if provided, skip the prompt and use these directly;
                        if None, prompt user before running.
    """
    cmd = [FFMPEG, "-progress", "pipe:"] + args
    used_extra = extra_args_preset

    if extra_args_preset is not None:
        cmd += extra_args_preset
    else:
        print(f"\n  \U0001f4cb 完整命令:")
        print(f"    {' '.join(str(a) for a in cmd)}")
        try:
            if confirm("是否添加自定义 FFmpeg 参数"):
                extra = input_required(
                    "请输入额外参数\n    示例: -b:a 192k -vf scale=1280:720")
                used_extra = shlex.split(extra)
                cmd += used_extra
                print(f"    已添加: {' '.join(used_extra)}")
        except Back:
            return False, None

    print(f"\n  \U0001f527 {description}...\n")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )

    total_sec = total_sec_hint
    current_sec = None
    speed_str = ""
    collected = []

    duration_re = re.compile(r"Duration: (\d+):(\d+):([\d.]+)")
    out_time_re = re.compile(r"out_time=(\d+):(\d+):([\d.]+)")
    speed_re = re.compile(r"speed=([\d.]+)x")

    for line in process.stdout: # type: ignore
        collected.append(line)

        if total_sec is None:
            m = duration_re.search(line)
            if m:
                h, m_, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                total_sec = h * 3600 + m_ * 60 + s

        m = out_time_re.match(line.strip())
        if m:
            h, m_, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            current_sec = h * 3600 + m_ * 60 + s
            _draw_progress_bar(current_sec, total_sec)

        m = speed_re.search(line)
        if m:
            speed_str = f" {m.group(1)}x"

    process.wait()

    final_val = current_sec or 0
    total_for_display = total_sec or final_val
    _draw_progress_bar(final_val, total_for_display, final=True)
    print()

    if process.returncode != 0:
        print(f"\n  ❌ {description}失败！")
        err_text = "".join(collected[-40:])
        shown = set()
        for ln in err_text.splitlines():
            ln = ln.strip()
            if not ln or ln in shown:
                continue
            low = ln.lower()
            if any(kw in low for kw in ("error", "invalid", "failed",
                                        "unable", "not found", "permission")):
                shown.add(ln)
                print(f"     {ln}")
        if collected:
            last = [l.strip() for l in collected if l.strip()]
            if last and last[-1] not in shown:
                print(f"     {last[-1]}")
        return False, used_extra

    print(f"  ✅ {description}完成！{speed_str}")
    return True, used_extra


# ── Operations ────────────────────────────────────────────────────

def op_format_convert(input_file: Path):
    """Format conversion for images / videos / audio."""
    ext = input_file.suffix.lower()
    category = "video" if ext in VIDEO_EXTS else ("image" if ext in IMAGE_EXTS else "audio")

    last_dir = Path()
    last_fmt = None
    last_extra = None
    settings_saved = False

    while True:
        # ── Output ──
        try:
            if settings_saved:
                name = input_required("输出文件名 (不含扩展名)")
                out_path = last_dir / f"{name}.{last_fmt}"
                print(f"    (目录: {last_dir}  格式: {last_fmt})")
            else:
                out_path, last_fmt = get_output_path(input_file, category, "操作选择")
                last_dir = out_path.parent
        except Back:
            return

        success, extra_used = run_ffmpeg(
            ["-i", str(input_file), "-y", str(out_path)],
            description="格式转换",
            extra_args_preset=last_extra if settings_saved else None,
        )
        if success:
            print(f"  输出文件: {out_path}")

        if not settings_saved:
            last_extra = extra_used or []

        print()
        try:
            if not confirm("是否继续将此文件转换为其他格式"):
                return
        except Back:
            return

        if not settings_saved:
            print()
            try:
                if confirm("是否记住本次设置，后续仅需输入文件名"):
                    settings_saved = True
                    print("  ✓ 已记住。")
            except Back:
                pass


def op_extract_audio(input_file: Path):
    """Extract audio from video — full or partial."""
    last_dir = Path()
    last_fmt = None
    last_extra = None
    settings_saved = False

    while True:  # restart from full/partial menu
        while True:
            print_header("\U0001f3b5 提取音频")
            print("    [1] 全部提取")
            print("    [2] 部分提取")
            print()
            print("    [b] 返回操作选择")
            choice = input("  > 请选择: ").strip().lower()
            if choice in ("b", "back", "返回", "上一步"):
                return
            if choice in ("1", "2"):
                break
            print("  ! 请输入 1 或 2，或输入 b 返回操作选择。")

        full = choice == "1"
        hint = None

        while True:
            if not full:
                try:
                    ss_raw, to_raw = get_time_range("全部/部分选择", "起始时间")
                except Back:
                    break
                dur = time_str_to_seconds(to_raw) - time_str_to_seconds(ss_raw)
                if dur <= 0:
                    print("  ! 结束时间必须大于起始时间。\n")
                    continue
                hint = dur
            else:
                ss_raw = to_raw = None

            # ── Output path ──────────────────────────────────────────
            try:
                if settings_saved:
                    name = input_required("输出文件名 (不含扩展名)")
                    out_path = last_dir / f"{name}.{last_fmt}"
                else:
                    out_path, last_fmt = get_output_path(
                        input_file, "audio",
                        "全部/部分选择" if full else "时间选择")
                    last_dir = out_path.parent
            except Back:
                if full:
                    break
                continue

            # ── Build command: -ss / -to after -i ────────────────────
            args = ["-i", str(input_file)]
            if ss_raw:
                args += ["-ss", ss_raw]
            if to_raw:
                args += ["-to", to_raw]
            args += ["-vn", "-y", str(out_path)]

            success, extra_used = run_ffmpeg(
                args,
                description="音频提取",
                total_sec_hint=hint,
                extra_args_preset=last_extra if settings_saved else None,
            )
            if not settings_saved:
                last_extra = extra_used or []
            if success:
                print(f"  输出文件: {out_path}")

            if full:
                return

            # ── Continue? ──
            print()
            try:
                if not confirm("是否继续提取同一视频的其他音频片段"):
                    return
            except Back:
                return

            # ── Remember settings (once, after first op) ──
            if not settings_saved:
                print()
                try:
                    if confirm("是否记住本次设置，后续仅需输入文件名"):
                        settings_saved = True
                        print("  ✓ 已记住。")
                except Back:
                    pass

            print("\n  ── 继续提取同一文件的其他片段 ──")


def op_clip_video(input_file: Path):
    """Clip a video segment."""
    last_dir = Path()
    last_fmt = None
    last_extra = None
    settings_saved = False

    while True:
        try:
            print_header("✂ 视频剪辑")
            ss_raw, to_raw = get_time_range("操作选择", "起始时间")
        except Back:
            return

        dur = time_str_to_seconds(to_raw) - time_str_to_seconds(ss_raw)
        if dur <= 0:
            print("  ! 结束时间必须大于起始时间。\n")
            continue

        # ── Output path ──────────────────────────────────────────
        try:
            if settings_saved:
                name = input_required("输出文件名 (不含扩展名)")
                out_path = last_dir / f"{name}.{last_fmt}"
            else:
                out_path, last_fmt = get_output_path(input_file, "video", "时间选择")
                last_dir = out_path.parent
        except Back:
            continue

        # ── Build command: -ss after -i ───────────────────────────
        args = [
            "-i", str(input_file),
            "-ss", ss_raw,
            "-to", to_raw,
            "-c", "copy",
            "-y", str(out_path),
        ]

        success, extra_used = run_ffmpeg(
            args,
            description="视频剪辑",
            total_sec_hint=dur,
            extra_args_preset=last_extra if settings_saved else None,
        )
        if not settings_saved:
            last_extra = extra_used or []
        if success:
            print(f"  输出文件: {out_path}")

        # ── Continue? ──
        print()
        try:
            if not confirm("是否继续剪辑同一视频的其他片段"):
                return
        except Back:
            return

        # ── Remember settings (once, after first op) ──
        if not settings_saved:
            print()
            try:
                if confirm("是否记住本次设置，后续仅需输入文件名"):
                    settings_saved = True
                    print("  ✓ 已记住。")
            except Back:
                pass

        print("\n  ── 继续剪辑同一文件的其他片段 ──")


def op_clip_audio(input_file: Path):
    """Clip an audio segment."""
    last_dir = Path()
    last_fmt = None
    last_extra = None
    settings_saved = False

    while True:
        try:
            print_header("✂ 音频剪辑")
            ss_raw, to_raw = get_time_range("操作选择", "起始时间")
        except Back:
            return

        dur = time_str_to_seconds(to_raw) - time_str_to_seconds(ss_raw)
        if dur <= 0:
            print("  ! 结束时间必须大于起始时间。\n")
            continue

        # ── Output path ──────────────────────────────────────────
        try:
            if settings_saved:
                name = input_required("输出文件名 (不含扩展名)")
                out_path = last_dir / f"{name}.{last_fmt}"
            else:
                out_path, last_fmt = get_output_path(input_file, "audio", "时间选择")
                last_dir = out_path.parent
        except Back:
            continue

        # ── Build command: -ss after -i ───────────────────────────
        args = [
            "-i", str(input_file),
            "-ss", ss_raw,
            "-to", to_raw,
            "-c", "copy",
            "-y", str(out_path),
        ]

        success, extra_used = run_ffmpeg(
            args,
            description="音频剪辑",
            total_sec_hint=dur,
            extra_args_preset=last_extra if settings_saved else None,
        )
        if not settings_saved:
            last_extra = extra_used or []
        if success:
            print(f"  输出文件: {out_path}")

        # ── Continue? ──
        print()
        try:
            if not confirm("是否继续剪辑同一音频的其他片段"):
                return
        except Back:
            return

        # ── Remember settings (once, after first op) ──
        if not settings_saved:
            print()
            try:
                if confirm("是否记住本次设置，后续仅需输入文件名"):
                    settings_saved = True
                    print("  ✓ 已记住。")
            except Back:
                pass

        print("\n  ── 继续剪辑同一文件的其他片段 ──")


# ── Main ──────────────────────────────────────────────────────────

def main():
    clear_screen()

    if FFMPEG is None:
        print_header("⚠ FFmpeg 未找到")
        print("  本程序依赖 FFmpeg 进行多媒体处理。")
        print()
        print("  Windows 安装方法:")
        print("    1. 访问 https://ffmpeg.org/download.html")
        print("    2. 下载 Windows 版本")
        print("    3. 将 ffmpeg.exe 所在目录添加到系统 PATH 环境变量")
        print("    4. 或将 ffmpeg.exe 放在本程序同目录下")
        print()
        input("  按 Enter 退出...")
        sys.exit(1)

    print_header("\U0001f3ac FFmpeg 多媒体处理工具")
    print("  支持功能:")
    print("    • 图片 / 视频 / 音频格式转换")
    print("    • 视频提取音频 (全部或部分)")
    print("    • 视频 / 音频剪辑")
    print()
    print("  提示: 在任何输入处输入 b / back / 返回 即可返回上一步")
    print()
    input("  按 Enter 开始...")

    while True:
        clear_screen()
        file_path = select_file()
        if file_path is None:
            break

        try:
            clear_screen()
            op_key, op_label = select_operation(file_path)
            clear_screen()
            print_header(f"\U0001f4c1 {file_path.name}  →  {op_label}")

            if op_key == "convert":
                op_format_convert(file_path)
            elif op_key == "extract_audio":
                op_extract_audio(file_path)
            elif op_key == "clip_video":
                op_clip_video(file_path)
            elif op_key == "clip_audio":
                op_clip_audio(file_path)
        except Back:
            pass

        print()
        input("  操作结束。按 Enter 返回文件选择列表...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  已中断。")
        sys.exit(0)
