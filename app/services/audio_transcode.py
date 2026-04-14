from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import settings


class AudioTranscodeError(RuntimeError):
    pass


SUPPORTED_AUDIO_EXTENSIONS = {
    '.amr', '.mp3', '.mpeg', '.wav', '.m4a', '.aac', '.ogg', '.opus', '.flac', '.wma',
}


def is_supported_audio_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def guess_audio_extension(filename: str, mime_type: str | None = None) -> str:
    suffix = Path(filename or '').suffix.lower()
    if suffix in SUPPORTED_AUDIO_EXTENSIONS:
        return suffix

    normalized_mime = (mime_type or '').split(';', 1)[0].strip().lower()
    mime_map = {
        'audio/amr': '.amr',
        'audio/3gpp': '.amr',
        'audio/mpeg': '.mp3',
        'audio/mp3': '.mp3',
        'audio/wav': '.wav',
        'audio/x-wav': '.wav',
        'audio/m4a': '.m4a',
        'audio/x-m4a': '.m4a',
        'audio/mp4': '.m4a',
        'audio/aac': '.aac',
        'audio/ogg': '.ogg',
        'audio/opus': '.opus',
        'audio/flac': '.flac',
        'audio/x-ms-wma': '.wma',
    }
    return mime_map.get(normalized_mime, suffix)


def is_supported_audio_upload(filename: str, mime_type: str | None = None) -> bool:
    return guess_audio_extension(filename, mime_type) in SUPPORTED_AUDIO_EXTENSIONS


def is_amr_filename(filename: str) -> bool:
    return guess_audio_extension(filename) == '.amr'


def ensure_ffmpeg_available() -> str:
    binary = (settings.ffmpeg_binary or 'ffmpeg').strip() or 'ffmpeg'
    resolved = shutil.which(binary) if Path(binary).name == binary else binary
    if not resolved or (Path(binary).name != binary and not Path(binary).exists()):
        raise AudioTranscodeError(
            '服务器当前未配置 ffmpeg，无法自动把音频转成 AMR。'
            ' 请安装 ffmpeg，或在 .env 中配置 FFMPEG_BINARY 指向 ffmpeg 可执行文件。'
        )
    return binary


def transcode_audio_to_amr(raw: bytes, filename: str) -> tuple[bytes, str, str]:
    ensure_ffmpeg_available()
    stem = Path(filename).stem or 'voice'
    output_filename = f'{stem}.amr'

    with tempfile.TemporaryDirectory(prefix='voice-transcode-') as tmpdir:
        input_path = Path(tmpdir) / filename
        output_path = Path(tmpdir) / output_filename
        input_path.write_bytes(raw)

        command = [
            settings.ffmpeg_binary or 'ffmpeg',
            '-y',
            '-i', str(input_path),
            '-ar', '8000',
            '-ac', '1',
            '-c:a', 'libopencore_amrnb',
            '-b:a', '12.2k',
            str(output_path),
        ]
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not output_path.exists():
            raise AudioTranscodeError('音频自动转 AMR 失败，请确认上传的是可解析的音频文件。')
        return output_path.read_bytes(), output_filename, 'audio/amr'
