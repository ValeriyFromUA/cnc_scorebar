"""Головний оверлей-скорбар: горизонтальна панель зверху по центру екрана,
завжди над усіма вікнами. Тактичний HUD-стиль із кутовими засічками.

Працює на Windows і macOS (на macOS прапор WindowStaysOnTopHint достатній
для тестування; "топмост над fullscreen-DirectX грою" — особливість Windows,
для якої нижче є best-effort фолбек через WinAPI).
"""

from __future__ import annotations

import math
import re
import sys

from PyQt6.QtCore import QRectF, Qt, QTimer, QPoint, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from data import Faction, FactionGroup, MatchState, Player, get_country, get_faction, get_player_color_hex
from themes import Theme, get_theme


def parse_color(value: str) -> QColor:
    """Підтримує "#RRGGBB" і "rgba(r, g, b, a)" (a у діапазоні 0-255)."""
    if value.startswith("rgba"):
        nums = [int(x) for x in re.findall(r"[\d.]+", value)]
        r, g, b, a = nums[:4]
        return QColor(r, g, b, a)
    return QColor(value)


# --------------------------------------------------------------------------
# Базова панель з кутовими засічками (tactical notch frame)
# --------------------------------------------------------------------------

class TacticalPanel(QFrame):
    def __init__(self, theme: Theme, bg_key: str = "bg", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.bg_key = bg_key
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        if theme.glow:
            glow = QGraphicsDropShadowEffect(self)
            glow.setColor(QColor(theme.border))
            glow.setBlurRadius(18)
            glow.setOffset(0, 0)
            self.setGraphicsEffect(glow)

    def set_theme(self, theme: Theme):
        self.theme = theme
        if theme.glow:
            glow = QGraphicsDropShadowEffect(self)
            glow.setColor(QColor(theme.border))
            glow.setBlurRadius(18)
            glow.setOffset(0, 0)
            self.setGraphicsEffect(glow)
        else:
            self.setGraphicsEffect(None)
        self.update()

    def _notch_path(self, n: int) -> QPainterPath:
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.moveTo(n, 0)
        path.lineTo(w - n, 0)
        path.lineTo(w, n)
        path.lineTo(w, h - n)
        path.lineTo(w - n, h)
        path.lineTo(n, h)
        path.lineTo(0, h - n)
        path.lineTo(0, n)
        path.closeSubpath()
        return path

    def _panel_path(self, w: int, h: int, n: int) -> QPainterPath:
        """Силует панелі залежно від theme.shape — щоб теми відрізнялись не
        лише кольором, а й формою рамки."""
        shape = self.theme.shape
        path = QPainterPath()
        if shape in ("brackets", "scanline", "concrete", "hazard"):
            path.addRect(0, 0, w, h)
        elif shape in ("carved", "glass"):
            radius = max(n, 6)
            path.addRoundedRect(0, 0, w, h, radius, radius)
        elif shape == "brushed":
            radius = max(n // 2, 3)
            path.addRoundedRect(0, 0, w, h, radius, radius)
        elif shape == "hexcut":
            # "Візор": скошені верхні кути, прямокутні нижні.
            path.moveTo(n, 0)
            path.lineTo(w - n, 0)
            path.lineTo(w, n)
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.lineTo(0, n)
            path.closeSubpath()
        elif shape == "diamond":
            # Асиметричний "карбоновий" зріз: лише верхньо-лівий і
            # нижньо-правий кути, два інші лишаються прямими.
            path.moveTo(n, 0)
            path.lineTo(w, 0)
            path.lineTo(w, h - n)
            path.lineTo(w - n, h)
            path.lineTo(0, h)
            path.lineTo(0, n)
            path.closeSubpath()
        elif shape == "toxic":
            path = self._toxic_path(w, h, n)
        else:  # "notch" — тактичний восьмикутник (CnC)
            path = self._notch_path(n)
        return path

    def _toxic_path(self, w: int, h: int, n: int) -> QPainterPath:
        """Хвиляста "ослизла" рамка — періодичні випуклості по периметру."""
        path = QPainterPath()
        step = 6
        amp = max(2.0, n / 3.0)
        pts: list[tuple[float, float]] = []
        x = 0.0
        while x <= w:
            pts.append((x, abs(amp * math.sin(x / 14.0))))
            x += step
        y = 0.0
        while y <= h:
            pts.append((w - abs(amp * math.sin(y / 14.0)), y))
            y += step
        x = float(w)
        while x >= 0:
            pts.append((x, h - abs(amp * math.sin(x / 14.0))))
            x -= step
        y = float(h)
        while y >= 0:
            pts.append((abs(amp * math.sin(y / 14.0)), y))
            y -= step
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                path.lineTo(px, py)
            path.closeSubpath()
        return path

    def _draw_corner_brackets(self, painter: QPainter, w: int, h: int):
        length = min(14, w // 6, h // 4)
        if length < 4:
            return
        pen = QPen(parse_color(self.theme.accent))
        pen.setWidthF(2.0)
        painter.setPen(pen)
        m = 3
        for x0, y0, dx, dy in (
            (m, m, 1, 1),
            (w - m, m, -1, 1),
            (m, h - m, 1, -1),
            (w - m, h - m, -1, -1),
        ):
            painter.drawLine(QPointF(x0, y0), QPointF(x0 + dx * length, y0))
            painter.drawLine(QPointF(x0, y0), QPointF(x0, y0 + dy * length))

    def _draw_scanlines(self, painter: QPainter, w: int, h: int):
        pen = QPen(parse_color(self.theme.border))
        pen.setWidthF(1.0)
        painter.save()
        painter.setOpacity(0.10)
        painter.setPen(pen)
        y = 4
        while y < h:
            painter.drawLine(0, y, w, y)
            y += 4
        painter.restore()

    def _draw_visor_seam(self, painter: QPainter, w: int, n: int):
        pen = QPen(parse_color(self.theme.accent))
        pen.setWidthF(1.0)
        painter.save()
        painter.setOpacity(0.55)
        painter.setPen(pen)
        painter.drawLine(n + 4, 4, w - n - 4, 4)
        painter.restore()

    def _draw_carbon_weave(self, painter: QPainter, path: QPainterPath, w: int, h: int):
        painter.save()
        painter.setClipPath(path)
        pen = QPen(parse_color(self.theme.accent_secondary))
        pen.setWidthF(1.0)
        painter.setOpacity(0.16)
        painter.setPen(pen)
        x = -h
        while x < w:
            painter.drawLine(x, h, x + h, 0)
            x += 6
        painter.restore()

    def _draw_glass_highlight(self, painter: QPainter, path: QPainterPath, w: int, h: int):
        painter.save()
        painter.setClipPath(path)
        grad = QLinearGradient(0, 0, 0, h * 0.6)
        grad.setColorAt(0.0, QColor(255, 255, 255, 90))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(0, 0, w, int(h * 0.6), grad)
        painter.restore()

    def _draw_carved_inner_line(self, painter: QPainter, w: int, h: int, n: int):
        inset = 4
        inner = QPainterPath()
        radius = max(n - 2, 2)
        inner.addRoundedRect(inset, inset, w - 2 * inset, h - 2 * inset, radius, radius)
        pen = QPen(parse_color(self.theme.accent_secondary))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(inner)

    def _draw_toxic_bubbles(self, painter: QPainter, w: int, h: int):
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        color = parse_color(self.theme.accent)
        bubbles = (
            (0.08, 0.72, 3.0), (0.18, 0.38, 2.0), (0.32, 0.8, 3.5),
            (0.5, 0.28, 2.0), (0.65, 0.7, 3.0), (0.8, 0.42, 2.0), (0.92, 0.78, 3.0),
        )
        for fx, fy, r in bubbles:
            painter.setOpacity(0.4)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(w * fx, h * fy), r, r)
        painter.restore()

    _CONCRETE_GRAYS = (
        QColor(255, 255, 255, 14), QColor(0, 0, 0, 18),
        QColor(255, 255, 255, 8), QColor(0, 0, 0, 10),
    )

    def _draw_concrete_texture(self, painter: QPainter, path: QPainterPath, w: int, h: int):
        """Кам'яно-сіра бетонна крапчаста текстура (Control: FBC)."""
        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        speckles = self._CONCRETE_GRAYS
        block = 7
        ix = 0
        x = 0
        while x < w:
            iy = 0
            y = 0
            while y < h:
                idx = (ix * 928371 + iy * 123457) % len(speckles)
                if idx != 2:  # лишаємо частину клітинок прозорими — менш регулярний візерунок
                    painter.setBrush(speckles[idx])
                    painter.drawRect(x, y, 3, 3)
                y += block
                iy += 1
            x += block
            ix += 1
        painter.restore()

        # тонкий темно-червоний "Hiss"-натяк — одна ледь помітна тріщина
        pen = QPen(parse_color(self.theme.accent_secondary))
        pen.setWidthF(1.0)
        painter.save()
        painter.setOpacity(0.5)
        painter.setPen(pen)
        painter.drawLine(QPointF(w * 0.15, h * 0.85), QPointF(w * 0.4, h * 0.55))
        painter.restore()

    def _draw_hazard_stripes(self, painter: QPainter, w: int, h: int):
        """Чорно-жовта смуга техніки безпеки вздовж верхнього й нижнього краю."""
        band = 5
        for y0 in (0, h - band):
            painter.save()
            painter.translate(0, y0)
            painter.setClipRect(0, 0, w, band)
            painter.setPen(Qt.PenStyle.NoPen)
            stripe_w = 10
            x = -band
            i = 0
            colors = (QColor(20, 20, 18), parse_color(self.theme.accent_secondary))
            while x < w + band:
                painter.setBrush(colors[i % 2])
                stripe = QPainterPath()
                stripe.moveTo(x, 0)
                stripe.lineTo(x + stripe_w, 0)
                stripe.lineTo(x + stripe_w - band, band)
                stripe.lineTo(x - band, band)
                stripe.closeSubpath()
                painter.drawPath(stripe)
                x += stripe_w
                i += 1
            painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        n = max(min(self.theme.notch, w // 4, h // 4), 0)
        shape = self.theme.shape
        path = self._panel_path(w, h, n)
        bg_value = self.theme.bg if self.bg_key == "bg" else self.theme.bg_alt
        base_color = parse_color(bg_value)

        if shape == "brushed":
            painter.save()
            painter.setClipPath(path)
            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(base_color).darker(115))
            grad.setColorAt(0.5, QColor(base_color).lighter(130))
            grad.setColorAt(1.0, QColor(base_color).darker(115))
            painter.fillRect(0, 0, w, h, grad)
            painter.restore()
        else:
            painter.fillPath(path, base_color)

        pen = QPen(parse_color(self.theme.border))
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.drawPath(path)

        if shape == "carved":
            self._draw_carved_inner_line(painter, w, h, n)
        elif shape in ("brackets", "scanline"):
            self._draw_corner_brackets(painter, w, h)
            if shape == "scanline":
                self._draw_scanlines(painter, w, h)
        elif shape == "hexcut":
            self._draw_visor_seam(painter, w, n)
        elif shape == "diamond":
            self._draw_carbon_weave(painter, path, w, h)
        elif shape == "glass":
            self._draw_glass_highlight(painter, path, w, h)
        elif shape == "toxic":
            self._draw_toxic_bubbles(painter, w, h)
        elif shape == "concrete":
            self._draw_concrete_texture(painter, path, w, h)
        elif shape == "hazard":
            self._draw_corner_brackets(painter, w, h)
            self._draw_hazard_stripes(painter, w, h)

        painter.end()


# --------------------------------------------------------------------------
# Іконка фракції — кругла "канатна" медаль як у генералів CnC Generals:
# Зеро Хаур (синя рамка = USA, червона = China, фіолетова = GLA),
# пісочне тло і чорний силует юніта/спецзагону, стилізована під тему.
# --------------------------------------------------------------------------

def _star_path(cx: float, cy: float, outer_r: float, inner_r: float, points: int = 5) -> QPainterPath:
    path = QPainterPath()
    step = math.pi / points
    rot = -math.pi / 2
    for i in range(points * 2):
        r = outer_r if i % 2 == 0 else inner_r
        angle = rot + i * step
        x, y = cx + r * math.cos(angle), cy + r * math.sin(angle)
        path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
    path.closeSubpath()
    return path


def _shield_path(cx: float, cy: float, size: float) -> QPainterPath:
    w, h = size * 0.95, size * 1.2
    path = QPainterPath()
    path.moveTo(cx - w / 2, cy - h / 2)
    path.lineTo(cx + w / 2, cy - h / 2)
    path.lineTo(cx + w / 2, cy)
    path.quadTo(cx + w / 2, cy + h / 2, cx, cy + h / 2)
    path.quadTo(cx - w / 2, cy + h / 2, cx - w / 2, cy)
    path.closeSubpath()
    return path


def _crescent_path(cx: float, cy: float, r: float) -> QPainterPath:
    outer = QPainterPath()
    outer.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    inner_r = r * 0.78
    offset = r * 0.5
    inner = QPainterPath()
    inner.addEllipse(QRectF(cx - inner_r + offset, cy - inner_r, 2 * inner_r, 2 * inner_r))
    return outer.subtracted(inner)


def _rotated(path: QPainterPath, deg: float, cx: float, cy: float) -> QPainterPath:
    t = QTransform()
    t.translate(cx, cy)
    t.rotate(deg)
    t.translate(-cx, -cy)
    return t.map(path)


def _spread_bird_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Пташка з розставленими крилами (геральдичний орел), фронтально:
    # плавні дуги крил (перо) + гострі виїмки між ними, маленька голова,
    # вузьке тіло з хвостом.
    path = QPainterPath()
    path.moveTo(cx, cy - s * 0.85)
    path.quadTo(cx + s * 0.25, cy - s * 0.78, cx + s * 0.35, cy - s * 0.55)
    path.quadTo(cx + s * 0.75, cy - s * 0.62, cx + s * 1.05, cy - s * 0.42)
    path.lineTo(cx + s * 0.55, cy - s * 0.22)
    path.quadTo(cx + s * 0.95, cy - s * 0.05, cx + s * 1.2, cy + s * 0.18)
    path.lineTo(cx + s * 0.5, cy + s * 0.08)
    path.quadTo(cx + s * 0.3, cy + s * 0.25, cx + s * 0.22, cy + s * 0.55)
    path.quadTo(cx + s * 0.12, cy + s * 0.72, cx, cy + s * 0.78)
    path.quadTo(cx - s * 0.12, cy + s * 0.72, cx - s * 0.22, cy + s * 0.55)
    path.quadTo(cx - s * 0.3, cy + s * 0.25, cx - s * 0.5, cy + s * 0.08)
    path.lineTo(cx - s * 1.2, cy + s * 0.18)
    path.quadTo(cx - s * 0.95, cy - s * 0.05, cx - s * 0.55, cy - s * 0.22)
    path.lineTo(cx - s * 1.05, cy - s * 0.42)
    path.quadTo(cx - s * 0.75, cy - s * 0.62, cx - s * 0.35, cy - s * 0.55)
    path.quadTo(cx - s * 0.25, cy - s * 0.78, cx, cy - s * 0.85)
    path.closeSubpath()
    return path


def _eagle_path(cx: float, cy: float, s: float) -> QPainterPath:
    # США (база) — щит, на фоні якого пташка з розставленими крилами.
    shield = _shield_path(cx, cy, s * 1.6)
    bird = _spread_bird_path(cx, cy, s * 0.6)
    return shield.subtracted(bird)


def _plane_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Авіація (USA Air Force) — силует "дельта" зверху.
    p = QPainterPath()
    p.moveTo(cx, cy - s)
    p.lineTo(cx + s * 0.9, cy + s * 0.55)
    p.lineTo(cx + s * 0.22, cy + s * 0.28)
    p.lineTo(cx, cy + s * 0.85)
    p.lineTo(cx - s * 0.22, cy + s * 0.28)
    p.lineTo(cx - s * 0.9, cy + s * 0.55)
    p.closeSubpath()
    return p


def _laser_beam_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Лазер (USA Laser General) — товстий лазерний промінь навскоси з джерелом.
    beam = QPainterPath()
    beam.moveTo(cx - s * 0.85, cy + s * 0.95)
    beam.lineTo(cx - s * 0.25, cy + s * 0.45)
    beam.lineTo(cx + s * 1.0, cy - s * 0.7)
    beam.lineTo(cx + s * 0.5, cy - s * 1.0)
    beam.lineTo(cx - s * 0.55, cy + s * 0.65)
    beam.closeSubpath()
    origin = QPainterPath()
    origin.addEllipse(QRectF(cx - s * 1.05, cy + s * 0.55, s * 0.55, s * 0.55))
    return beam.united(origin)


def _bolt_path(cx: float, cy: float, s: float) -> QPainterPath:
    bolt = QPainterPath()
    bolt.moveTo(cx + s * 0.18, cy - s * 0.95)
    bolt.lineTo(cx - s * 0.22, cy + s * 0.05)
    bolt.lineTo(cx + s * 0.02, cy + s * 0.05)
    bolt.lineTo(cx - s * 0.18, cy + s * 1.05)
    bolt.lineTo(cx + s * 0.32, cy - s * 0.05)
    bolt.lineTo(cx + s * 0.02, cy - s * 0.05)
    bolt.closeSubpath()
    return bolt


def _star5_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Китай (база) — комуністична п'ятикутна зірка.
    return _star_path(cx, cy, s, s * 0.42)


def _ak_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Піхота (China Infantry General) — силует АК-47: ствол, приклад,
    # пістолетна рукоятка і впізнаваний вигнутий "банановий" магазин.
    receiver = QPainterPath()
    receiver.addRoundedRect(QRectF(cx - s * 1.05, cy - s * 0.16, s * 1.6, s * 0.24), s * 0.05, s * 0.05)
    stock = QPainterPath()
    stock.addRoundedRect(QRectF(cx + s * 0.5, cy - s * 0.1, s * 0.5, s * 0.26), s * 0.05, s * 0.05)
    grip = QPainterPath()
    grip.addRoundedRect(QRectF(cx + s * 0.08, cy + s * 0.06, s * 0.22, s * 0.5), s * 0.05, s * 0.05)
    grip = _rotated(grip, 18, cx + s * 0.19, cy + s * 0.06)
    mag = QPainterPath()
    mag.moveTo(cx - s * 0.32, cy + s * 0.08)
    mag.cubicTo(cx - s * 0.18, cy + s * 0.55, cx - s * 0.55, cy + s * 1.0, cx - s * 0.8, cy + s * 1.15)
    mag.lineTo(cx - s * 0.58, cy + s * 1.2)
    mag.cubicTo(cx - s * 0.42, cy + s * 0.75, cx - s * 0.08, cy + s * 0.38, cx - s * 0.02, cy + s * 0.1)
    mag.closeSubpath()
    combined = receiver.united(stock).united(grip).united(mag)
    return _rotated(combined, -16, cx, cy)


def _tank_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Танки (China Tank General) — силует танка з гарматою.
    body = QPainterPath()
    body.addRoundedRect(QRectF(cx - s * 0.85, cy + s * 0.05, s * 1.7, s * 0.5), s * 0.1, s * 0.1)
    turret = QPainterPath()
    turret.addEllipse(QRectF(cx - s * 0.4, cy - s * 0.45, s * 0.8, s * 0.55))
    barrel = QPainterPath()
    barrel.addRoundedRect(QRectF(cx + s * 0.05, cy - s * 0.3, s * 0.85, s * 0.16), s * 0.04, s * 0.04)
    return body.united(turret).united(barrel)


def _wedge_path(cx: float, cy: float, r1: float, r2: float, start_deg: float, sweep_deg: float) -> QPainterPath:
    path = QPainterPath()
    outer = QRectF(cx - r2, cy - r2, 2 * r2, 2 * r2)
    inner = QRectF(cx - r1, cy - r1, 2 * r1, 2 * r1)
    path.arcMoveTo(outer, start_deg)
    path.arcTo(outer, start_deg, sweep_deg)
    path.arcTo(inner, start_deg + sweep_deg, -sweep_deg)
    path.closeSubpath()
    return path


def _radiation_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Ядерна зброя (China Nuke General) — знак радіації.
    combined = QPainterPath()
    combined.addEllipse(QRectF(cx - s * 0.22, cy - s * 0.22, s * 0.44, s * 0.44))
    for i in range(3):
        combined.addPath(_wedge_path(cx, cy, s * 0.34, s * 0.95, -90 + i * 120 - 25, 50))
    return combined


def _dagger_blade_path(cx: float, cy: float, length: float, angle_deg: float) -> QPainterPath:
    # Тонке лезо кинджала (ромб з гострим вістрям і потовщеним середником).
    blade = QPainterPath()
    blade.moveTo(cx, cy - length * 0.5)
    blade.lineTo(cx + length * 0.1, cy + length * 0.18)
    blade.lineTo(cx + length * 0.05, cy + length * 0.5)
    blade.lineTo(cx - length * 0.05, cy + length * 0.5)
    blade.lineTo(cx - length * 0.1, cy + length * 0.18)
    blade.closeSubpath()
    return _rotated(blade, angle_deg, cx, cy)


def _crescent_daggers_path(cx: float, cy: float, s: float) -> QPainterPath:
    # GLA (база) — два кинджали навхрест на фоні великого півмісяця (роги вниз).
    moon_r = s * 0.95
    outer = QPainterPath()
    outer.addEllipse(QRectF(cx - moon_r, cy - moon_r, 2 * moon_r, 2 * moon_r))
    inner_r = moon_r * 0.78
    inner = QPainterPath()
    inner.addEllipse(QRectF(cx - inner_r, cy - inner_r - moon_r * 0.5, 2 * inner_r, 2 * inner_r))
    crescent = outer.subtracted(inner)
    crescent = _rotated(crescent, 90, cx, cy)

    d1 = _dagger_blade_path(cx, cy, s * 1.7, 45)
    d2 = _dagger_blade_path(cx, cy, s * 1.7, -45)
    return crescent.united(d1).united(d2)


def _dynamite_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Підрив (GLA Demolition General) — одна велика динамітна шашка з ґнотом.
    stick = QPainterPath()
    stick.addRoundedRect(QRectF(cx - s * 0.4, cy - s * 0.85, s * 0.8, s * 1.65), s * 0.14, s * 0.14)
    fuse = QPainterPath()
    fuse.addRoundedRect(QRectF(cx - s * 0.07, cy - s * 1.25, s * 0.14, s * 0.45), s * 0.04, s * 0.04)
    fuse = _rotated(fuse, 25, cx, cy - s * 0.85)
    return stick.united(fuse)


def _bone_path(cx: float, cy: float, length: float, angle_deg: float) -> QPainterPath:
    bar = QPainterPath()
    bar.addRoundedRect(QRectF(cx - length / 2, cy - length * 0.08, length, length * 0.16), length * 0.08, length * 0.08)
    knob1 = QPainterPath()
    knob1.addEllipse(QRectF(cx - length / 2 - length * 0.09, cy - length * 0.16, length * 0.24, length * 0.24))
    knob2 = QPainterPath()
    knob2.addEllipse(QRectF(cx + length / 2 - length * 0.15, cy - length * 0.16, length * 0.24, length * 0.24))
    combined = bar.united(knob1).united(knob2)
    return _rotated(combined, angle_deg, cx, cy)


def _toxic_path(cx: float, cy: float, s: float) -> QPainterPath:
    # Токсини (GLA Toxin General) — череп зі схрещеними кістками.
    skull = QPainterPath()
    skull.addEllipse(QRectF(cx - s * 0.55, cy - s * 0.85, s * 1.1, s * 0.95))
    jaw = QPainterPath()
    jaw.addRoundedRect(QRectF(cx - s * 0.3, cy - s * 0.15, s * 0.6, s * 0.3), s * 0.06, s * 0.06)
    skull = skull.united(jaw)
    eye1 = QPainterPath()
    eye1.addEllipse(QRectF(cx - s * 0.34, cy - s * 0.6, s * 0.24, s * 0.28))
    eye2 = QPainterPath()
    eye2.addEllipse(QRectF(cx + s * 0.1, cy - s * 0.6, s * 0.24, s * 0.28))
    skull = skull.subtracted(eye1).subtracted(eye2)
    b1 = _bone_path(cx, cy + s * 0.55, s * 1.3, 35)
    b2 = _bone_path(cx, cy + s * 0.55, s * 1.3, -35)
    return skull.united(b1).united(b2)


# Кожному ключу під-фракції відповідає конкретний силует генерала.
GLYPH_BUILDERS = {
    "usa": _eagle_path,
    "usa_air": _plane_path,
    "usa_laser": _laser_beam_path,
    "usa_super": None,  # малюється окремо: щит + білий патч-блискавка
    "china": _star5_path,
    "china_inf": _ak_path,
    "china_tank": _tank_path,
    "china_nuke": _radiation_path,
    "gla": _crescent_daggers_path,
    "gla_demo": _dynamite_path,
    "gla_stealth": None,  # малюється окремо: приціл/перехрестя
    "gla_toxin": _toxic_path,
}

# Двоколірна гама медалі за групою фракції: Китай — червоний+золотий,
# США — синій+білий, GLA — зелений+жовтий (зовнішнє кільце / акцентне
# кільце / тло-підкладка).
GROUP_STYLE = {
    FactionGroup.USA: ("#1C4F9C", "#FFFFFF", "#E7EFFB"),
    FactionGroup.CHINA: ("#B23A2E", "#D4AF37", "#F6E6B8"),
    FactionGroup.GLA: ("#3F6B2B", "#D4C13B", "#ECE7A8"),
}

_INK = QColor(32, 24, 16)


class FactionBadge(QWidget):
    """Кругла медаль-значок фракції/генерала у стилі іконок генералів
    CnC Generals: кільце кольору групи (USA синьо-білий, China червоно-
    золотий, GLA зелено-жовтий) і чорний силует конкретного юніта.
    """

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.faction: Faction | None = None
        self.setFixedSize(32, 32)

    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()

    def set_faction(self, faction: Faction):
        self.faction = faction
        self.setToolTip(faction.name)
        self.update()

    def paintEvent(self, event):
        if not self.faction:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 0.5

        ring_hex, trim_hex, fill_hex = GROUP_STYLE.get(self.faction.group, GROUP_STYLE[FactionGroup.USA])
        ring_color = QColor(ring_hex)

        outer = QPainterPath()
        outer.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        trim = QPainterPath()
        trim_r = r * 0.84
        trim.addEllipse(QRectF(cx - trim_r, cy - trim_r, 2 * trim_r, 2 * trim_r))
        inner = QPainterPath()
        inner_r = r * 0.7
        inner.addEllipse(QRectF(cx - inner_r, cy - inner_r, 2 * inner_r, 2 * inner_r))

        if self.theme.key in ("metal", "carbon"):
            grad = QLinearGradient(0, cy - r, 0, cy + r)
            grad.setColorAt(0.0, ring_color.lighter(140))
            grad.setColorAt(0.6, ring_color)
            grad.setColorAt(1.0, ring_color.darker(150))
            painter.fillPath(outer, grad)
        else:
            painter.fillPath(outer, ring_color)

        painter.fillPath(trim, QColor(trim_hex))

        fill_color = QColor(fill_hex)
        if self.theme.key == "glass":
            fill_color.setAlpha(215)
        painter.fillPath(inner, fill_color)

        border_pen = QPen(parse_color(self.theme.border))
        border_pen.setWidthF(1.1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(outer)

        if self.theme.glow:
            glow_pen = QPen(parse_color(self.theme.accent))
            glow_pen.setWidthF(0.8)
            painter.setPen(glow_pen)
            painter.drawEllipse(QRectF(cx - r - 0.6, cy - r - 0.6, 2 * (r + 0.6), 2 * (r + 0.6)))

        builder = GLYPH_BUILDERS.get(self.faction.key)
        glyph_size = inner_r * 0.88
        if self.faction.key == "gla_stealth":
            painter.setPen(QPen(_INK, 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for ring_r in (glyph_size * 0.45, glyph_size * 0.85):
                painter.drawEllipse(QRectF(cx - ring_r, cy - ring_r, 2 * ring_r, 2 * ring_r))
            cross = glyph_size * 1.25
            painter.drawLine(QPointF(cx - cross, cy), QPointF(cx + cross, cy))
            painter.drawLine(QPointF(cx, cy - cross), QPointF(cx, cy + cross))
            painter.setBrush(_INK)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - 1.0, cy - 1.0, 2.0, 2.0))
        elif self.faction.key == "usa_super":
            shield = _shield_path(cx, cy, glyph_size * 1.6)
            bolt = _bolt_path(cx, cy, glyph_size)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_INK)
            painter.drawPath(shield)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawPath(bolt)
        elif builder is not None:
            glyph = builder(cx, cy, glyph_size)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_INK)
            painter.drawPath(glyph)
        painter.end()


# --------------------------------------------------------------------------
# Рядок гравця
# --------------------------------------------------------------------------

class ColorTag(QWidget):
    """Маленький кольоровий трикутник-маркер гравця: одна сторона прилягає
    до зовнішньої рамки командної панелі, а вершина (кут) показує в бік
    гравця (всередину рядка)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(9)
        self._color: str | None = None
        self._point_right = True

    def set_color(self, color_hex: str | None, point_right: bool):
        self._color = color_hex
        self._point_right = point_right
        self.update()

    def paintEvent(self, event):
        if not self._color:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        w, h = self.width(), self.height()
        path = QPainterPath()
        if self._point_right:
            path.moveTo(0, h * 0.2)
            path.lineTo(0, h * 0.8)
            path.lineTo(w, h * 0.5)
        else:
            path.moveTo(w, h * 0.2)
            path.lineTo(w, h * 0.8)
            path.lineTo(0, h * 0.5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()


class PlayerRow(QWidget):
    NAME_WIDTH = 120

    def __init__(
        self,
        theme: Theme,
        show_rank: bool = False,
        show_score: bool = False,
        mirrored: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.show_rank = show_rank
        self.show_score = show_score
        self.mirrored = mirrored

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        self.rank_label = QLabel("")
        self.rank_label.setFixedWidth(16)
        self.flag_label = QLabel("")
        self.flag_label.setFixedWidth(24)
        self.flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label = QLabel("Player")
        # Фіксована ширина імені (з елайдингом), щоб обидві командні панелі
        # завжди мали однакову загальну ширину незалежно від довжини ніка —
        # це потрібно, щоб рахунок/заголовок лишались строго по центру.
        self.name_label.setFixedWidth(self.NAME_WIDTH)
        # ELO/дивізіон гравця (з cnc-general-ukraine.org), якщо обрано зі списку.
        self.rating_label = QLabel("")
        self.rating_label.setFixedWidth(44)
        self.rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge = FactionBadge(theme)
        self.score_label = QLabel("0")
        self.score_label.setFixedWidth(28)
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # Кольоровий трикутник-маркер гравця — завжди прилягає до
        # зовнішнього краю рядка (краю командної панелі), вершиною
        # всередину, в бік гравця.
        self.color_tag = ColorTag()

        if mirrored:
            # Дзеркальне розташування для правої команди: прапор країни
            # лишається на зовнішньому краю (тепер праворуч), а фракція —
            # завжди ближче до центру скорбару. Рейтинг (дивізіон/ELO)
            # завжди між прапором і ніком.
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if show_score:
                layout.addWidget(self.score_label)
            layout.addWidget(self.badge)
            layout.addWidget(self.name_label)
            layout.addWidget(self.rating_label)
            layout.addWidget(self.flag_label)
            if show_rank:
                layout.addWidget(self.rank_label)
            layout.addWidget(self.color_tag)
        else:
            layout.addWidget(self.color_tag)
            if show_rank:
                layout.addWidget(self.rank_label)
            layout.addWidget(self.flag_label)
            layout.addWidget(self.rating_label)
            layout.addWidget(self.name_label)
            layout.addWidget(self.badge)
            if show_score:
                layout.addWidget(self.score_label)

        self._apply_fonts()

    def _apply_fonts(self):
        flag_font = QFont(self.theme.font_family.split(",")[0].strip())
        flag_font.setPointSize(13)
        self.flag_label.setFont(flag_font)

        name_font = QFont(self.theme.font_family.split(",")[0].strip())
        name_font.setPointSize(11)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet(f"color: {self.theme.text_primary}; background: transparent;")

        rank_font = QFont(name_font)
        rank_font.setBold(False)
        self.rank_label.setFont(rank_font)
        self.rank_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

        self.score_label.setFont(name_font)
        self.score_label.setStyleSheet(f"color: {self.theme.accent}; background: transparent;")

        rating_font = QFont(self.theme.font_family.split(",")[0].strip())
        rating_font.setPointSize(8)
        self.rating_label.setFont(rating_font)
        self.rating_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

    def set_theme(self, theme: Theme):
        self.theme = theme
        self._apply_fonts()
        self.badge.set_theme(theme)
        self.update_player(self._last_player, self._last_rank)

    _last_player: Player | None = None
    _last_rank: int | None = None

    def update_player(self, player: Player, rank: int | None = None):
        self._last_player = player
        self._last_rank = rank
        country = get_country(player.country_code)
        faction = get_faction(player.faction_key)

        self.flag_label.setText(country.flag)
        name_text = player.name or "—"
        metrics = QFontMetrics(self.name_label.font())
        # Лімітуємо ширину константою (а не .width()), бо віджет може ще не
        # пройти layout-пас на момент першого update_player().
        elided = metrics.elidedText(name_text, Qt.TextElideMode.ElideRight, self.NAME_WIDTH - 4)
        self.name_label.setText(elided)
        self.name_label.setToolTip(name_text)
        self.badge.set_faction(faction)
        self.color_tag.set_color(get_player_color_hex(player.color_key), point_right=not self.mirrored)

        # Дивізіон показуємо лише якщо це одна з ліг A/B/C/D —
        # "Player", "Division E" чи відсутній дивізіон не відображаємо.
        rating_parts = []
        if player.division:
            division_letter = player.division.removeprefix("Division ").strip().upper()
            if division_letter in ("A", "B", "C", "D"):
                rating_parts.append(division_letter)
        if player.elo is not None:
            rating_parts.append(str(player.elo))
        self.rating_label.setText(" · ".join(rating_parts))

        if self.show_score:
            self.score_label.setText(str(player.score))
        if self.show_rank:
            self.rank_label.setText(f"{rank}." if rank else "")


# --------------------------------------------------------------------------
# Командна панель (список гравців однієї сторони)
# --------------------------------------------------------------------------

class TeamPanel(TacticalPanel):
    def __init__(self, theme: Theme, side: str, parent=None):
        super().__init__(theme, bg_key="bg", parent=parent)
        self.side = side  # "left" / "right"
        self.rows: list[PlayerRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.notch + 4, 6, theme.notch + 4, 6)
        outer.setSpacing(2)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(2)
        outer.addLayout(self.rows_layout)

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self.layout().setContentsMargins(theme.notch + 4, 6, theme.notch + 4, 6)
        for row in self.rows:
            row.set_theme(theme)

    def set_size(self, n: int):
        while len(self.rows) < n:
            # Права команда дзеркальна: прапор країни лишається на
            # зовнішньому краю панелі, а фракція — ближче до центру.
            row = PlayerRow(self.theme, show_rank=False, show_score=False, mirrored=(self.side == "right"))
            self.rows.append(row)
            self.rows_layout.addWidget(row)
        while len(self.rows) > n:
            row = self.rows.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()

    def update_players(self, players: list[Player]):
        self.set_size(len(players))
        for row, player in zip(self.rows, players):
            row.update_player(player)


# --------------------------------------------------------------------------
# Центральна панель з рахунком
# --------------------------------------------------------------------------

class CenterScorePanel(TacticalPanel):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(theme, bg_key="bg_alt", parent=parent)
        self.setMinimumWidth(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.notch + 8, 6, theme.notch + 8, 6)
        layout.setSpacing(0)

        self.mode_label = QLabel("1v1")
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.score_label = QLabel("0 : 0")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.map_label = QLabel("")
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.mode_label)
        layout.addWidget(self.score_label)
        layout.addWidget(self.map_label)

        self._apply_fonts()

    def _apply_fonts(self):
        family = self.theme.font_family.split(",")[0].strip()

        mode_font = QFont(family)
        mode_font.setPointSize(9)
        self.mode_label.setFont(mode_font)
        self.mode_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

        score_font = QFont(family)
        score_font.setPointSize(20)
        score_font.setBold(True)
        self.score_label.setFont(score_font)
        self.score_label.setStyleSheet(f"color: {self.theme.accent}; background: transparent;")

        map_font = QFont(family)
        map_font.setPointSize(8)
        self.map_label.setFont(map_font)
        self.map_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self._apply_fonts()

    def update_state(self, state: MatchState):
        self.mode_label.setText(state.mode_label)
        self.score_label.setText(f"{state.score_a} : {state.score_b}")
        self.map_label.setText(state.map_name)


# --------------------------------------------------------------------------
# FFA панель
# --------------------------------------------------------------------------

class FFAPanel(TacticalPanel):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(theme, bg_key="bg", parent=parent)
        self.rows: list[PlayerRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.notch + 4, 6, theme.notch + 4, 6)
        outer.setSpacing(2)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(2)
        outer.addLayout(self.rows_layout)

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self.layout().setContentsMargins(theme.notch + 4, 6, theme.notch + 4, 6)
        for row in self.rows:
            row.set_theme(theme)

    def set_size(self, n: int):
        while len(self.rows) < n:
            row = PlayerRow(self.theme, show_rank=True, show_score=True)
            self.rows.append(row)
            self.rows_layout.addWidget(row)
        while len(self.rows) > n:
            row = self.rows.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()

    def update_players(self, players: list[Player]):
        ordered = sorted(players, key=lambda p: p.score, reverse=True)
        self.set_size(len(ordered))
        for i, (row, player) in enumerate(zip(self.rows, ordered), start=1):
            row.update_player(player, rank=i)


# --------------------------------------------------------------------------
# Заголовок
# --------------------------------------------------------------------------

class TitleLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(36)
        self._title = "SCOREBAR"
        self.setText(self._title)

    def set_title(self, title: str):
        self._title = title or "SCOREBAR"
        self.setText(self._title)

    def set_theme(self, theme: Theme):
        self.setStyleSheet(
            f"color: {theme.accent}; background: transparent; "
            f"font-weight: bold; letter-spacing: 2px;"
        )


# --------------------------------------------------------------------------
# Головне вікно оверлею
# --------------------------------------------------------------------------

class ScorebarWindow(QWidget):
    def __init__(self, theme_key: str = "cnc"):
        super().__init__()
        self.theme = get_theme(theme_key)
        self.state = MatchState(ffa=False, team_size=1, players=[Player(team=0), Player(team=1)])
        self.position_key = "top_center"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # На macOS вікна з прапором Qt.WindowType.Tool за умовчанням ховаються,
        # коли застосунок втрачає активність (тобто при перемиканні на іншу
        # гру/вікно) — цей атрибут вимикає таку поведінку.
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        # Оверлей ніколи не повинен перехоплювати клавіатуру — з нею працює
        # лише панель керування.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.row_widget = QWidget()
        self.row_layout = QHBoxLayout(self.row_widget)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(4)
        root.addWidget(self.row_widget)

        self.title_label = TitleLabel()
        root.addWidget(self.title_label)

        self.left_panel = TeamPanel(self.theme, "left")
        self.center_panel = CenterScorePanel(self.theme)
        self.right_panel = TeamPanel(self.theme, "right")
        self.ffa_panel = FFAPanel(self.theme)

        self.row_layout.addWidget(self.left_panel)
        self.row_layout.addWidget(self.center_panel)
        self.row_layout.addWidget(self.right_panel)
        self.row_layout.addWidget(self.ffa_panel)

        self.title_label.set_theme(self.theme)
        self.refresh()

        # Windows: best-effort, повторно встановлюємо topmost через WinAPI,
        # бо повноекранні DirectX-гри інколи "відбирають" topmost. На інших
        # платформах НЕ робимо періодичний self.raise_() — він перехоплює
        # фокус клавіатури і блокує введення в панелі керування; там
        # WindowStaysOnTopHint (вище) сам тримає вікно нагорі без активації.
        if sys.platform.startswith("win"):
            self._topmost_timer = QTimer(self)
            self._topmost_timer.timeout.connect(self._reassert_topmost_windows)
            self._topmost_timer.start(2000)

    # ------------------------------------------------------------------
    def _reassert_topmost_windows(self):
        try:
            import ctypes

            hwnd = int(self.winId())
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    def set_match(self, state: MatchState):
        self.state = state
        self.refresh()

    def set_theme(self, theme_key: str):
        self.theme = get_theme(theme_key)
        self.left_panel.set_theme(self.theme)
        self.right_panel.set_theme(self.theme)
        self.center_panel.set_theme(self.theme)
        self.ffa_panel.set_theme(self.theme)
        self.title_label.set_theme(self.theme)
        self.refresh()

    def set_title(self, title: str):
        self.title_label.set_title(title)
        self.adjustSize()
        self.reposition()

    def increment_score(self, side: str, delta: int = 1):
        if side == "a":
            self.state.score_a = max(0, self.state.score_a + delta)
        elif side == "b":
            self.state.score_b = max(0, self.state.score_b + delta)
        self.center_panel.update_state(self.state)

    def increment_player_score(self, index: int, delta: int = 1):
        if 0 <= index < len(self.state.players):
            self.state.players[index].score = max(0, self.state.players[index].score + delta)
            self.refresh()

    def refresh(self):
        ffa = self.state.ffa
        self.left_panel.setVisible(not ffa)
        self.center_panel.setVisible(not ffa)
        self.right_panel.setVisible(not ffa)
        self.ffa_panel.setVisible(ffa)

        if ffa:
            self.ffa_panel.update_players(self.state.players)
        else:
            team_a = [p for p in self.state.players if p.team == 0]
            team_b = [p for p in self.state.players if p.team == 1]
            self.left_panel.update_players(team_a)
            self.right_panel.update_players(team_b)
            self.center_panel.update_state(self.state)

        # Перемикання team/FFA ховає/показує цілі панелі — без явної
        # інвалідації layout-кеш Qt інколи лишає старі (більші) розміри
        # прихованих віджетів, і adjustSize() не стискає вікно назад.
        self.row_layout.invalidate()
        self.row_layout.activate()
        self.layout().invalidate()
        self.layout().activate()
        self.adjustSize()
        self.reposition()

    def set_position(self, position_key: str):
        self.position_key = position_key
        self.reposition()

    def reposition(self, margin: int = 6):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        if self.position_key == "left_middle":
            x = geo.x() + margin
            y = geo.y() + (geo.height() - self.height()) // 2
        elif self.position_key == "right_middle":
            x = geo.x() + geo.width() - self.width() - margin
            y = geo.y() + (geo.height() - self.height()) // 2
        else:  # "top_center" — дефолтна позиція
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + margin
        self.move(QPoint(x, y))

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ScorebarWindow()
    win.show()
    sys.exit(app.exec())
