"""
Lógica de divisão de MP3 usando ffmpeg.
"""

import os
import subprocess
from typing import Callable


def find_ffmpeg() -> str | None:
    """Procura ffmpeg: mesma pasta do script, depois PATH."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
    if os.path.isfile(here):
        return here
    # PATH
    import shutil
    return shutil.which("ffmpeg")


def get_mp3_duration(input_mp3: str, ffmpeg_path: str | None = None) -> int | None:
    """Retorna duração do MP3 em segundos usando ffprobe, ou None se indisponível."""
    if ffmpeg_path is None:
        ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        return None
    ffprobe = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if not os.path.isfile(ffprobe):
        import shutil
        ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_mp3],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return int(float(result.stdout.strip()))
    except Exception:
        pass
    return None


def seconds_to_hhmmss(s: int) -> str:
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def safe_name(text: str) -> str:
    for ch in r'\/:*?"<>|':
        text = text.replace(ch, "")
    return text.strip()


def split_album(
    input_mp3: str,
    tracks: list[tuple[str, int]],   # [(titulo, duracao_segundos), ...]
    output_dir: str,
    artist: str = "",
    album: str = "",
    year: str = "",
    ffmpeg_path: str | None = None,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[str]:
    """
    Divide o MP3 nas faixas indicadas.
    progress_cb(faixa_atual, total, mensagem)
    Retorna lista de arquivos criados.
    """
    if ffmpeg_path is None:
        ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        raise FileNotFoundError("ffmpeg não encontrado. Coloque ffmpeg.exe na pasta do app ou adicione ao PATH.")

    os.makedirs(output_dir, exist_ok=True)

    starts = []
    current = 0
    for _, dur in tracks:
        starts.append(current)
        current += dur

    created = []
    total = len(tracks)

    for i, (title, dur) in enumerate(tracks):
        track_num = i + 1
        start = starts[i]

        prefix = " - ".join(filter(None, [safe_name(artist), safe_name(album)]))
        out_file = os.path.join(output_dir, f"{prefix} - {track_num:02d} - {safe_name(title)}.mp3")

        cmd = [
            ffmpeg_path, "-y",
            "-ss", seconds_to_hhmmss(start),
            "-i", input_mp3,
        ]

        # Última faixa: sem -t (vai até o fim do arquivo)
        if i < total - 1:
            cmd += ["-t", str(dur)]

        if title:
            cmd += ["-metadata", f"title={title}"]
        if artist:
            cmd += ["-metadata", f"artist={artist}"]
        if album:
            cmd += ["-metadata", f"album={album}"]
        if year:
            cmd += ["-metadata", f"date={year}"]
        cmd += [
            "-metadata", f"track={track_num}/{total}",
            "-acodec", "copy",
            out_file,
        ]

        if progress_cb:
            progress_cb(track_num, total, f"[{track_num}/{total}] {title}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Erro ao extrair faixa {track_num}:\n{result.stderr[-400:]}")

        created.append(out_file)

    return created
