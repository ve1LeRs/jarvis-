"""Screen / selection helpers: clipboard, OCR, click-by-text."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from jarvis.actions import launch
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
    image_path = _latest_screenshot()
    if not image_path:
        return shot_msg + " Не нашёл файл скриншота для распознавания."

    ocr_text = _ocr_image(image_path)
    if ocr_text:
        preview = ocr_text if len(ocr_text) <= 450 else ocr_text[:447] + "..."
        return f"На экране вижу текст: {preview}"
    return (
        f"{shot_msg} "
        "Распознавание текста недоступно (нужен tesseract). "
        "Могу прочитать выделение из буфера: скажите «прочитай выделение»."
    )


def _pictures_dir() -> Path:
    pictures = Path.home() / "Pictures"
    if not pictures.exists():
        alt = Path.home() / "Изображения"
        if alt.exists():
            return alt
    return pictures


def _latest_screenshot() -> Path | None:
    pictures = _pictures_dir()
    if not pictures.exists():
        return None
    images = sorted(pictures.glob("JARVIS_*.png"), reverse=True)
    return images[0] if images else None


def _ocr_image(path: Path) -> str:
    if shutil.which("tesseract"):
        out_base = Path(tempfile.gettempdir()) / "jarvis_ocr"
        try:
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
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        return " ".join(pytesseract.image_to_string(Image.open(path), lang="rus+eng").split())
    except Exception:
        return ""


def _ocr_boxes(path: Path) -> list[dict]:
    """Return word boxes [{text,x,y,w,h}] using tesseract TSV when available."""
    boxes: list[dict] = []
    if shutil.which("tesseract"):
        try:
            completed = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "rus+eng", "tsv"],
                check=False,
                capture_output=True,
                text=True,
            )
            lines = (completed.stdout or "").splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split("\t")
                    if len(parts) < 12:
                        continue
                    try:
                        conf = float(parts[10])
                    except ValueError:
                        conf = -1
                    text = parts[11].strip()
                    if conf < 40 or not text:
                        continue
                    try:
                        left, top, width, height = map(int, parts[6:10])
                    except ValueError:
                        continue
                    boxes.append(
                        {
                            "text": text,
                            "x": left + width // 2,
                            "y": top + height // 2,
                            "w": width,
                            "h": height,
                        }
                    )
                return boxes
        except Exception:
            pass
    try:
        import pytesseract  # type: ignore
        from PIL import Image

        data = pytesseract.image_to_data(Image.open(path), lang="rus+eng", output_type=pytesseract.Output.DICT)
        n = len(data.get("text") or [])
        for i in range(n):
            text = str(data["text"][i]).strip()
            try:
                conf = float(data["conf"][i])
            except ValueError:
                conf = -1
            if not text or conf < 40:
                continue
            x = int(data["left"][i]) + int(data["width"][i]) // 2
            y = int(data["top"][i]) + int(data["height"][i]) // 2
            boxes.append({"text": text, "x": x, "y": y, "w": int(data["width"][i]), "h": int(data["height"][i])})
    except Exception:
        return []
    return boxes


def _click_at(x: int, y: int) -> bool:
    if launch.SYSTEM != "Windows":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.05)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
        return True
    except Exception:
        return False


def click_text(query: str) -> str:
    """Screenshot → OCR → click the word/phrase matching query."""
    needle = (query or "").strip()
    if not needle:
        return "Скажите, что нажать. Например: нажми кнопку Сохранить."
    shot_msg = sys_act.take_screenshot()
    image_path = _latest_screenshot()
    if not image_path:
        return shot_msg + " Нет скриншота для поиска кнопки."

    boxes = _ocr_boxes(image_path)
    if not boxes:
        # Fallback: at least OCR text
        text = _ocr_image(image_path)
        if text and needle.lower() in text.lower():
            return (
                f"Вижу «{needle}» на экране, но координаты недоступны "
                "(нужен tesseract tsv). Установите tesseract."
            )
        return f"Не нашёл «{needle}» на экране. {shot_msg}"

    needle_l = needle.lower()
    # Prefer exact word, then substring
    candidates = [b for b in boxes if b["text"].lower() == needle_l]
    if not candidates:
        candidates = [b for b in boxes if needle_l in b["text"].lower()]
    if not candidates:
        # Multi-word: find sequence of boxes
        words = re.findall(r"\w+", needle_l, flags=re.UNICODE)
        if len(words) >= 2:
            texts = [b["text"].lower() for b in boxes]
            for i in range(len(texts) - len(words) + 1):
                if texts[i : i + len(words)] == words:
                    candidates = [boxes[i]]
                    break
    if not candidates:
        return f"Не нашёл «{needle}» среди распознанного текста."

    target = candidates[0]
    if _click_at(int(target["x"]), int(target["y"])):
        return f"Нажимаю «{target['text']}» на экране."
    return (
        f"Нашёл «{target['text']}» около ({target['x']}, {target['y']}), "
        "но клик доступен только на Windows."
    )
