"""Screen / selection helpers: clipboard and optional OCR."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from jarvis.actions import system as sys_act


def read_selection() -> str:
    """Read current clipboard as the user's selection."""
    text = sys_act.read_clipboard()
    if text.startswith("В буфере:"):
        body = text[len("В буфере:") :].strip()
        if not body or body == "Буфер обмена пуст.":
            return "Буфер пуст. Выделите текст и скопируйте (Ctrl+C), затем повторите."
        preview = body if len(body) <= 500 else body[:497] + "..."
        return f"В выделении: {preview}"
    return text


def whats_on_screen() -> str:
    """Take a screenshot and try OCR; fall back to a helpful message."""
    shot_msg = sys_act.take_screenshot()
    # Find newest JARVIS_*.png in Pictures
    pictures = Path.home() / "Pictures"
    if not pictures.exists():
        pictures = Path.home() / "Изображения"
    images = sorted(pictures.glob("JARVIS_*.png"), reverse=True) if pictures.exists() else []
    if not images:
        return shot_msg + " Не нашёл файл скриншота для распознавания."

    image_path = images[0]
    ocr_text = _ocr_image(image_path)
    if ocr_text:
        preview = ocr_text if len(ocr_text) <= 450 else ocr_text[:447] + "..."
        return f"На экране вижу текст: {preview}"
    return (
        f"{shot_msg} "
        "Распознавание текста недоступно (нужен tesseract). "
        "Могу прочитать выделение из буфера: скажите «прочитай выделение»."
    )


def _ocr_image(path: Path) -> str:
    # Prefer tesseract CLI if installed.
    if shutil.which("tesseract"):
        out_base = Path(tempfile.gettempdir()) / "jarvis_ocr"
        try:
            import subprocess

            subprocess.run(
                ["tesseract", str(path), str(out_base), "-l", "rus+eng"],
                check=False,
                capture_output=True,
            )
            txt_path = Path(str(out_base) + ".txt")
            if txt_path.exists():
                return " ".join(txt_path.read_text(encoding="utf-8", errors="ignore").split())
        except Exception:
            return ""
    # Optional pytesseract
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        return " ".join(pytesseract.image_to_string(Image.open(path), lang="rus+eng").split())
    except Exception:
        return ""
