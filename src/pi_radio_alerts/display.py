from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread
from time import monotonic, sleep, strftime
from collections import OrderedDict
import logging
import os

from PIL import Image, ImageDraw, ImageFont


LOG = logging.getLogger(__name__)


@dataclass
class DisplaySnapshot:
    alerts: list[str]
    healthy: bool
    error_text: str | None


class DisplayController:
    def __init__(
        self,
        *,
        hold_seconds: int = 120,
        rows: int = 16,
        cols: int = 32,
        hardware_mapping: str = "adafruit-hat-pwm",
        brightness: int = 40,
    ) -> None:
        self._hold_seconds = hold_seconds
        self._alerts: OrderedDict[str, float] = OrderedDict()
        self._healthy = True
        self._error_text: str | None = None
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._rows = rows
        self._cols = cols
        self._brightness = brightness
        self._matrix = None
        self._font = ImageFont.load_default()
        self._hardware_mapping = hardware_mapping
        self._console_mode = os.environ.get("PI_RADIO_ALERTS_CONSOLE", "").lower() in {"1", "true"}
        self._last_console_text = ""
        self._init_matrix()

    def _init_matrix(self) -> None:
        if self._console_mode:
            LOG.info("Running in console display mode.")
            return
        try:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions

            options = RGBMatrixOptions()
            options.rows = self._rows
            options.cols = self._cols
            options.chain_length = 1
            options.parallel = 1
            options.hardware_mapping = self._hardware_mapping
            options.brightness = self._brightness
            self._matrix = RGBMatrix(options=options)
        except Exception as exc:  # pragma: no cover
            LOG.warning("Falling back to console display mode: %s", exc)
            self._console_mode = True

    def start(self) -> None:
        self._thread = Thread(target=self._run, name="display-controller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def show_alert(self, text: str) -> None:
        with self._lock:
            self._alerts[text] = monotonic() + self._hold_seconds
        LOG.info("Displaying alert: %s", text)

    def set_healthy(self) -> None:
        with self._lock:
            self._healthy = True
            self._error_text = None

    def set_error(self, message: str = "ERROR") -> None:
        with self._lock:
            self._healthy = False
            self._error_text = message or "ERROR"

    def _snapshot(self) -> DisplaySnapshot:
        now = monotonic()
        with self._lock:
            expired = [name for name, expires_at in self._alerts.items() if expires_at <= now]
            for name in expired:
                self._alerts.pop(name, None)
            return DisplaySnapshot(
                alerts=list(self._alerts.keys()),
                healthy=self._healthy,
                error_text=self._error_text,
            )

    def _run(self) -> None:
        offset = self._cols
        while not self._stop_event.is_set():
            snapshot = self._snapshot()
            if not snapshot.healthy:
                self._render_error(snapshot.error_text or "ERROR")
                offset = self._cols
                sleep(0.25)
                continue

            if not snapshot.alerts:
                self._render_idle()
                offset = self._cols
                sleep(0.12)
                continue

            offset = self._render_scrolling_alerts(snapshot.alerts, offset)
            sleep(0.06)

    def _render_idle(self) -> None:
        idle_text = strftime("%H:%M")
        image = Image.new("RGB", (self._cols, self._rows), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        bbox = self._font.getbbox(idle_text)
        text_x = (self._cols - bbox[2]) // 2
        text_y = max(0, ((self._rows - 2) - bbox[3]) // 2)
        draw.text((text_x, text_y), idle_text, font=self._font, fill=(255, 80, 0))
        self._draw_health_indicator(draw, healthy=True)
        self._present(image, f"IDLE: {idle_text}")

    def _render_scrolling_alerts(self, alerts: list[str], offset: int) -> int:
        image = Image.new("RGB", (self._cols, self._rows), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        x = offset
        colors = ((255, 215, 0), (0, 180, 255))
        separator = ", "

        for index, alert in enumerate(alerts):
            color = colors[index % len(colors)]
            draw.text((x, 0), alert, font=self._font, fill=color)
            x += self._font.getbbox(alert)[2]
            if index < len(alerts) - 1:
                draw.text((x, 0), separator, font=self._font, fill=(255, 255, 255))
                x += self._font.getbbox(separator)[2]

        self._draw_health_indicator(draw, healthy=True)
        self._present(image, f"ALERTS: {separator.join(alerts)}")
        text_width = max(0, x - offset)
        next_offset = offset - 1
        if next_offset < -text_width:
            return self._cols
        return next_offset

    def _render_error(self, text: str) -> None:
        image = Image.new("RGB", (self._cols, self._rows), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, self._cols - 1, self._rows - 1), fill=(255, 0, 0))
        bbox = self._font.getbbox(text)
        x = (self._cols - bbox[2]) // 2
        y = (self._rows - bbox[3]) // 2
        draw.text((x, y), text, font=self._font, fill=(0, 0, 0))
        self._present(image, f"ERROR: {text}")

    def _draw_health_indicator(self, draw: ImageDraw.ImageDraw, *, healthy: bool) -> None:
        indicator_on = healthy and int(monotonic() * 2) % 2 == 0
        fill = (120, 255, 120) if indicator_on else (0, 50, 0)
        y0 = self._rows - 2
        draw.rectangle((0, y0, self._cols - 1, self._rows - 1), fill=(0, 0, 0))
        draw.rectangle((self._cols - 4, y0, self._cols - 1, self._rows - 1), fill=fill)

    def _present(self, image: Image.Image, console_text: str) -> None:
        if self._console_mode:
            if console_text != self._last_console_text:
                LOG.info("DISPLAY: %s", console_text)
                self._last_console_text = console_text
            return

        self._matrix.SetImage(image.convert("RGB"))
