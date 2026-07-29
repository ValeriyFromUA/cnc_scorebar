"""Головний оверлей-скорбар: горизонтальна панель зверху по центру екрана.
Тактичний HUD-стиль із кутовими засічками.

Позиція "завжди зверху" — опційна (перемикач у панелі керування, за
замовчуванням вимкнено): вікно не використовує Qt.WindowType.Tool, щоб
лишатись звичайним, легко впізнаваним вікном для захоплення в OBS (Tool-вікна
Windows часто не потрапляють у список джерел "Window Capture"). Якщо "завжди
зверху" ввімкнено на Windows, нижче є best-effort фолбек через WinAPI, бо
повноекранні DirectX-ігри інколи "відбирають" topmost.
"""

from __future__ import annotations

import math
import re
import sys
from functools import lru_cache

from PyQt6.QtCore import QRectF, Qt, QTimer, QPoint, QPointF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from data import Faction, MatchState, Player, get_country, get_faction, get_player_color_hex
from themes import Theme, get_default_icon_variant, get_theme


@lru_cache(maxsize=256)
def _load_pixmap(path: str) -> QPixmap:
    """Кеш завантажених іконок (прапори, бейджі фракцій) — файли з диска
    читаються максимум один раз за увесь час роботи застосунку."""
    return QPixmap(path)


def make_font(font_family: str) -> QFont:
    """QFont з повним ланцюжком фолбеків ("Eurostile, Arial Narrow, ...").
    Якщо першого шрифту немає в системі (типова ситуація на Windows, де
    немає Eurostile/Bank Gothic), Qt візьме наступний із переліку, а не
    підставить системний дефолт."""
    font = QFont()
    font.setFamilies([f.strip() for f in font_family.split(",") if f.strip()])
    return font


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
        # Глобальний перемикач світіння (вкладка "Сумісність"): ефекти
        # QGraphicsDropShadowEffect на layered-вікнах Windows інколи дають
        # артефакти або просідання FPS.
        self._glow_enabled = True
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._apply_glow()

    def _apply_glow(self):
        if self.theme.glow and self._glow_enabled:
            glow = QGraphicsDropShadowEffect(self)
            glow.setColor(QColor(self.theme.border))
            glow.setBlurRadius(18)
            glow.setOffset(0, 0)
            self.setGraphicsEffect(glow)
        else:
            self.setGraphicsEffect(None)

    def set_glow_enabled(self, enabled: bool):
        self._glow_enabled = enabled
        self._apply_glow()
        self.update()

    def set_theme(self, theme: Theme):
        self.theme = theme
        self._apply_glow()
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
# Іконка фракції — оригінальне зображення генерала з гри (Icons/Generals,
# кольоровий варіант blue/orng/slvr) або лого армії групи (Icons/Armies) для
# базової фракції.
# --------------------------------------------------------------------------

class FactionBadge(QWidget):
    """Значок фракції/генерала — оригінальна іконка з гри, без ручного
    малювання. Колірний варіант (blue/orng/slvr) спільний для всього
    скорбару, див. ScorebarWindow.set_icon_variant()."""

    def __init__(self, theme: Theme, icon_variant: str = "blue", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.faction: Faction | None = None
        self.icon_variant = icon_variant
        self.setFixedSize(38, 38)

    def set_theme(self, theme: Theme):
        self.theme = theme
        self.update()

    def set_icon_variant(self, variant: str):
        if variant != self.icon_variant:
            self.icon_variant = variant
            self.update()

    def set_faction(self, faction: Faction):
        self.faction = faction
        self.setToolTip(faction.name)
        self.update()

    def paintEvent(self, event):
        if not self.faction:
            return
        pixmap = _load_pixmap(str(self.faction.icon_path(self.icon_variant)))
        if pixmap.isNull():
            return
        w, h = self.width(), self.height()
        scaled = pixmap.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        painter.end()


# --------------------------------------------------------------------------
# Рядок гравця
# --------------------------------------------------------------------------

class ColorTag(QWidget):
    """Кольоровий маркер гравця біля зовнішнього краю рядка. Два режими
    малювання: "triangle" — трикутник вершиною всередину рядка (в бік
    гравця), "edge" — суцільна смуга на всю висоту рядка впритул до
    зовнішнього краю картки. Режим "underline" цим віджетом не малюється —
    рядок його ховає і підкреслює нік стилем."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(9)
        self._color: str | None = None
        self._point_right = True
        self._style = "triangle"

    def set_color(self, color_hex: str | None, point_right: bool):
        self._color = color_hex
        self._point_right = point_right
        self.update()

    def set_style(self, style: str):
        if style != self._style:
            self._style = style
            self.update()

    def paintEvent(self, event):
        if not self._color:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        w, h = self.width(), self.height()
        if self._style == "edge":
            # Смугу до краю картки малює сама панель (_draw_edge_color_bands):
            # цей віджет стоїть за внутрішніми полями картки й фізично не
            # може дотягтися до рамки, тож тут не малюємо нічого.
            painter.end()
            return
        else:  # "triangle"
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
    MIN_NAME_WIDTH = 60

    def __init__(
        self,
        theme: Theme,
        show_rank: bool = False,
        show_score: bool = False,
        mirrored: bool = False,
        icon_variant: str = "blue",
        name_font_size: int = 11,
        elo_font_size: int = 13,
        color_style: str = "triangle",
        parent=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.show_rank = show_rank
        self.show_score = show_score
        self.mirrored = mirrored
        self.name_font_size = name_font_size
        self.elo_font_size = elo_font_size
        self.color_style = color_style
        self._color_hex: str | None = None

        layout = QHBoxLayout(self)
        # Вертикальних внутрішніх полів немає навмисно: відстань між рядками
        # повністю задається налаштуванням "відступ між ніками" (spacing
        # rows_layout панелі), щоб нуль означав справді впритул.
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        self.rank_label = QLabel("")
        self.rank_label.setFixedWidth(16)
        self.flag_label = QLabel("")
        self.flag_label.setFixedSize(24, 16)
        self.flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label = QLabel("Player")
        # Нік завжди по центру свого поля — інакше короткі ніки "липнуть"
        # до краю, коли ширина підігнана під найдовший нік.
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ширина імені однакова для всіх рядків і задається ззовні
        # (ScorebarWindow підганяє її під найдовший нік серед усіх гравців) —
        # так обидві командні панелі мають однакову загальну ширину, і
        # рахунок/заголовок лишаються строго по центру.
        self.name_label.setFixedWidth(self.MIN_NAME_WIDTH)
        # ELO гравця (з cnc-general-ukraine.org або введене вручну).
        # Ширина поля виставляється в _apply_fonts за метриками шрифту.
        self.rating_label = QLabel("")
        self.rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge = FactionBadge(theme, icon_variant)
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
            # завжди ближче до центру скорбару. Рейтинг (ELO) завжди між
            # прапором і ніком.
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

    def _name_stylesheet(self) -> str:
        style = f"color: {self.theme.text_primary}; background: transparent;"
        if self.color_style == "underline" and self._color_hex:
            style += f" border-bottom: 2px solid {self._color_hex};"
        return style

    def _apply_fonts(self):
        name_font = make_font(self.theme.font_family)
        name_font.setPointSize(self.name_font_size)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        self.name_label.setStyleSheet(self._name_stylesheet())

        rank_font = QFont(name_font)
        rank_font.setBold(False)
        self.rank_label.setFont(rank_font)
        self.rank_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

        self.score_label.setFont(name_font)
        self.score_label.setStyleSheet(f"color: {self.theme.accent}; background: transparent;")

        rating_font = make_font(self.theme.font_family)
        rating_font.setPointSize(self.elo_font_size)
        self.rating_label.setFont(rating_font)
        # Ширина під 4-значне ELO — інакше при більшому шрифті число
        # обрізалось би фіксованою шириною.
        self.rating_label.setFixedWidth(QFontMetrics(rating_font).horizontalAdvance("8888") + 6)
        self.rating_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

    def set_theme(self, theme: Theme):
        self.theme = theme
        self._apply_fonts()
        self.badge.set_theme(theme)
        self.update_player(self._last_player, self._last_rank)

    def set_icon_variant(self, variant: str):
        self.badge.set_icon_variant(variant)

    def set_name_font_size(self, size: int):
        self.name_font_size = size
        self._apply_fonts()

    def set_elo_font_size(self, size: int):
        self.elo_font_size = size
        self._apply_fonts()

    def set_color_style(self, style: str):
        self.color_style = style
        self._apply_color_marker()

    def _apply_color_marker(self):
        # "underline" малюється підкресленням ніка, окремий віджет-маркер
        # тоді не потрібен і ховається (симетрично для обох команд).
        self.color_tag.setVisible(self.color_style != "underline")
        self.color_tag.set_style(self.color_style)
        self.color_tag.set_color(self._color_hex, point_right=not self.mirrored)
        self.name_label.setStyleSheet(self._name_stylesheet())

    def set_name_width(self, width: int):
        self.name_label.setFixedWidth(max(width, self.MIN_NAME_WIDTH))

    _last_player: Player | None = None
    _last_rank: int | None = None

    def update_player(self, player: Player, rank: int | None = None):
        self._last_player = player
        self._last_rank = rank
        country = get_country(player.country_code)
        faction = get_faction(player.faction_key)

        flag_pixmap = _load_pixmap(str(country.flag_path))
        if flag_pixmap.isNull():
            self.flag_label.clear()
        else:
            scaled_flag = flag_pixmap.scaled(
                24, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.flag_label.setPixmap(scaled_flag)
        self.flag_label.setToolTip(country.name)
        name_text = player.name or "—"
        self.name_label.setText(name_text)
        self.name_label.setToolTip(name_text)
        self.badge.set_faction(faction)
        self._color_hex = get_player_color_hex(player.color_key)
        self._apply_color_marker()

        # На скорбарі показуємо лише ELO — дивізіон зберігається в даних
        # гравця, але не відображається.
        self.rating_label.setText(str(player.elo) if player.elo is not None else "")

        if self.show_score:
            self.score_label.setText(str(player.score))
        if self.show_rank:
            self.rank_label.setText(f"{rank}." if rank else "")


def _draw_edge_color_bands(panel: TacticalPanel, rows: list[PlayerRow], left_side: bool):
    """Режим "зафарбований край": той самий трикутник-маркер гравця, але
    його основа лежить на самому краю картки, а вершина — на звичному місці
    маркера (вістрям у бік гравця). Малюється панеллю (а не
    віджетом-маркером), бо лише панель може зафарбувати зону своїх
    внутрішніх полів; кліп по силуету рамки, щоб трикутник повторював форму
    картки (зрізані кути тощо)."""
    w, h = panel.width(), panel.height()
    n = max(min(panel.theme.notch, w // 4, h // 4), 0)
    path = panel._panel_path(w, h, n)
    painter = QPainter(panel)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)
    painter.setPen(Qt.PenStyle.NoPen)
    for row in rows:
        if not row._color_hex:
            continue
        geo = row.geometry()
        tag_pos = row.color_tag.mapTo(panel, QPoint(0, 0))
        y0, row_h = geo.y(), geo.height()
        painter.setBrush(QColor(row._color_hex))
        triangle = QPainterPath()
        if left_side:
            apex_x = tag_pos.x() + row.color_tag.width()
            triangle.moveTo(0, y0 + row_h * 0.2)
            triangle.lineTo(0, y0 + row_h * 0.8)
            triangle.lineTo(apex_x, y0 + row_h * 0.5)
        else:
            apex_x = tag_pos.x()
            triangle.moveTo(w, y0 + row_h * 0.2)
            triangle.lineTo(w, y0 + row_h * 0.8)
            triangle.lineTo(apex_x, y0 + row_h * 0.5)
        triangle.closeSubpath()
        painter.drawPath(triangle)
    # Рамку домальовуємо поверх смуг, щоб контур картки лишався чітким.
    painter.setClipping(False)
    pen = QPen(parse_color(panel.theme.border))
    pen.setWidthF(1.2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.end()


# --------------------------------------------------------------------------
# Командна панель (список гравців однієї сторони)
# --------------------------------------------------------------------------

class TeamPanel(TacticalPanel):
    def __init__(self, theme: Theme, side: str, icon_variant: str = "blue", parent=None):
        super().__init__(theme, bg_key="bg", parent=parent)
        self.side = side  # "left" / "right"
        self.icon_variant = icon_variant
        self.rows: list[PlayerRow] = []
        self.name_font_size = 11
        self.elo_font_size = 13
        self.row_spacing = 4
        self.v_padding = 6
        self.color_style = "triangle"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.notch + 4, self.v_padding, theme.notch + 4, self.v_padding)
        outer.setSpacing(2)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(self.row_spacing)
        outer.addLayout(self.rows_layout)

    def _apply_margins(self):
        self.layout().setContentsMargins(
            self.theme.notch + 4, self.v_padding, self.theme.notch + 4, self.v_padding
        )

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self._apply_margins()
        for row in self.rows:
            row.set_theme(theme)

    def set_icon_variant(self, variant: str):
        self.icon_variant = variant
        for row in self.rows:
            row.set_icon_variant(variant)

    def set_name_font_size(self, size: int):
        self.name_font_size = size
        for row in self.rows:
            row.set_name_font_size(size)

    def set_elo_font_size(self, size: int):
        self.elo_font_size = size
        for row in self.rows:
            row.set_elo_font_size(size)

    def set_color_style(self, style: str):
        self.color_style = style
        for row in self.rows:
            row.set_color_style(style)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.color_style == "edge":
            _draw_edge_color_bands(self, self.rows, left_side=(self.side == "left"))

    def set_row_spacing(self, spacing: int):
        self.row_spacing = spacing
        self.rows_layout.setSpacing(spacing)

    def set_vertical_padding(self, padding: int):
        self.v_padding = padding
        self._apply_margins()

    def set_size(self, n: int):
        while len(self.rows) < n:
            # Права команда дзеркальна: прапор країни лишається на
            # зовнішньому краю панелі, а фракція — ближче до центру.
            row = PlayerRow(
                self.theme,
                show_rank=False,
                show_score=False,
                mirrored=(self.side == "right"),
                icon_variant=self.icon_variant,
                name_font_size=self.name_font_size,
                elo_font_size=self.elo_font_size,
                color_style=self.color_style,
            )
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
        # Кольори гравців могли змінитись — смуги "зафарбованого краю"
        # малює сама панель, тож їй потрібен власний repaint.
        self.update()


# --------------------------------------------------------------------------
# Центральна панель з рахунком
# --------------------------------------------------------------------------

class CenterScorePanel(TacticalPanel):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(theme, bg_key="bg_alt", parent=parent)
        self.setMinimumWidth(150)
        self.score_font_size = 20

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.notch + 8, 6, theme.notch + 8, 6)
        layout.setSpacing(0)

        self.score_label = QLabel("0 : 0")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.map_label = QLabel("")
        self.map_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Розпірки зверху/знизу тримають блок рахунок+карта строго по
        # вертикальному центру панелі, коли бокові панелі вищі за неї.
        layout.addStretch(1)
        layout.addWidget(self.score_label)
        layout.addWidget(self.map_label)
        layout.addStretch(1)

        self._apply_fonts()

    def _apply_fonts(self):
        score_font = make_font(self.theme.font_family)
        score_font.setPointSize(self.score_font_size)
        score_font.setBold(True)
        self.score_label.setFont(score_font)
        self.score_label.setStyleSheet(f"color: {self.theme.accent}; background: transparent;")

        map_font = make_font(self.theme.font_family)
        map_font.setPointSize(8)
        self.map_label.setFont(map_font)
        self.map_label.setStyleSheet(f"color: {self.theme.text_secondary}; background: transparent;")

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self._apply_fonts()

    def set_score_font_size(self, size: int):
        self.score_font_size = size
        self._apply_fonts()

    def update_state(self, state: MatchState):
        self.score_label.setText(f"{state.score_a} : {state.score_b}")
        self.map_label.setText(state.map_name)
        # Порожній рядок карти ховаємо повністю, інакше він займає висоту
        # і зсуває рахунок догори від центру.
        self.map_label.setVisible(bool(state.map_name))


# --------------------------------------------------------------------------
# FFA панель
# --------------------------------------------------------------------------

class FFAPanel(TacticalPanel):
    def __init__(self, theme: Theme, icon_variant: str = "blue", parent=None):
        super().__init__(theme, bg_key="bg", parent=parent)
        self.icon_variant = icon_variant
        self.rows: list[PlayerRow] = []
        self.name_font_size = 11
        self.elo_font_size = 13
        self.row_spacing = 4
        self.v_padding = 6
        self.color_style = "triangle"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.notch + 4, self.v_padding, theme.notch + 4, self.v_padding)
        outer.setSpacing(2)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(self.row_spacing)
        outer.addLayout(self.rows_layout)

    def _apply_margins(self):
        self.layout().setContentsMargins(
            self.theme.notch + 4, self.v_padding, self.theme.notch + 4, self.v_padding
        )

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self._apply_margins()
        for row in self.rows:
            row.set_theme(theme)

    def set_icon_variant(self, variant: str):
        self.icon_variant = variant
        for row in self.rows:
            row.set_icon_variant(variant)

    def set_name_font_size(self, size: int):
        self.name_font_size = size
        for row in self.rows:
            row.set_name_font_size(size)

    def set_elo_font_size(self, size: int):
        self.elo_font_size = size
        for row in self.rows:
            row.set_elo_font_size(size)

    def set_color_style(self, style: str):
        self.color_style = style
        for row in self.rows:
            row.set_color_style(style)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.color_style == "edge":
            _draw_edge_color_bands(self, self.rows, left_side=True)

    def set_row_spacing(self, spacing: int):
        self.row_spacing = spacing
        self.rows_layout.setSpacing(spacing)

    def set_vertical_padding(self, padding: int):
        self.v_padding = padding
        self._apply_margins()

    def set_size(self, n: int):
        while len(self.rows) < n:
            row = PlayerRow(
                self.theme,
                show_rank=True,
                show_score=True,
                icon_variant=self.icon_variant,
                name_font_size=self.name_font_size,
                elo_font_size=self.elo_font_size,
                color_style=self.color_style,
            )
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
        self.update()


# --------------------------------------------------------------------------
# Заголовок
# --------------------------------------------------------------------------

class TitlePanel(TacticalPanel):
    """Заголовок на власній підкладці в стилі теми — та сама tactical-рамка
    (форма, фон, рамка), що й у панелей скорбару."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(theme, bg_key="bg_alt", parent=parent)
        self.title_font_size = 11
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.notch + 12, 4, theme.notch + 12, 4)
        self.label = QLabel("SCOREBAR")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        self._apply_fonts()

    def set_title(self, title: str):
        self.label.setText(title or "SCOREBAR")

    def set_title_font_size(self, size: int):
        self.title_font_size = size
        self._apply_fonts()

    def set_theme(self, theme: Theme):
        super().set_theme(theme)
        self.layout().setContentsMargins(theme.notch + 12, 4, theme.notch + 12, 4)
        self._apply_fonts()

    def _apply_fonts(self):
        font = make_font(self.theme.font_family)
        font.setPointSize(self.title_font_size)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setStyleSheet(
            f"color: {self.theme.accent}; background: transparent; letter-spacing: 2px;"
        )


# --------------------------------------------------------------------------
# Головне вікно оверлею
# --------------------------------------------------------------------------

class ScorebarWindow(QWidget):
    def __init__(self, theme_key: str = "cnc"):
        super().__init__()
        self.theme = get_theme(theme_key)
        self.icon_variant = get_default_icon_variant(theme_key)
        self.state = MatchState(ffa=False, team_size=1, players=[Player(team=0), Player(team=1)])
        self.position_key = "top_center"
        self.screen_index = 0
        self._always_on_top = False
        self._topmost_timer: QTimer | None = None
        self._solid_bg = False
        self._solid_bg_color = "#000000"

        # Заголовок вікна — щоб оверлей легко впізнавався в списку джерел
        # "Window Capture" в OBS.
        self.setWindowTitle("Scorebar Overlay")
        # Без Qt.WindowType.Tool: на Windows цей флаг ставить WS_EX_TOOLWINDOW,
        # через що OBS (та інші засоби переліку вікон) часто не бачать таке
        # вікно у списку джерел захоплення.
        self.setWindowFlags(self._window_flags())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        # Оверлей ніколи не повинен перехоплювати клавіатуру — з нею працює
        # лише панель керування.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        # Вікно завжди точно дорівнює вмісту: і росте, і стискається назад —
        # без цього Qt лишає вікну стару (більшу) ширину, а зайвий простір
        # розтягує центральну панель, зсуваючи рахунок з центру екрана.
        root.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.row_widget = QWidget()
        self.row_layout = QHBoxLayout(self.row_widget)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(4)
        root.addWidget(self.row_widget)

        # Заголовок на тематичній підкладці, по центру, шириною під текст.
        self.title_panel = TitlePanel(self.theme)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addStretch(1)
        title_row.addWidget(self.title_panel)
        title_row.addStretch(1)
        root.addLayout(title_row)

        self.left_panel = TeamPanel(self.theme, "left", self.icon_variant)
        self.center_panel = CenterScorePanel(self.theme)
        self.right_panel = TeamPanel(self.theme, "right", self.icon_variant)
        self.ffa_panel = FFAPanel(self.theme, self.icon_variant)

        self.row_layout.addWidget(self.left_panel)
        self.row_layout.addWidget(self.center_panel)
        self.row_layout.addWidget(self.right_panel)
        self.row_layout.addWidget(self.ffa_panel)

        self.refresh()

    # ------------------------------------------------------------------
    def _window_flags(self) -> Qt.WindowType:
        flags = Qt.WindowType.FramelessWindowHint
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags

    def set_always_on_top(self, enabled: bool):
        """"Завжди зверху" — вимкнено за замовчуванням: OBS компонує джерело
        в сцену незалежно від реального порядку вікон на екрані, тож
        topmost потрібен лише якщо скорбар мають бачити поверх гри й поза OBS."""
        if enabled == self._always_on_top:
            return
        self._always_on_top = enabled
        was_visible = self.isVisible()
        self.setWindowFlags(self._window_flags())
        if was_visible:
            self.show()
        self.reposition()

        if sys.platform.startswith("win"):
            if enabled:
                if self._topmost_timer is None:
                    self._topmost_timer = QTimer(self)
                    self._topmost_timer.timeout.connect(self._reassert_topmost_windows)
                self._topmost_timer.start(2000)
            elif self._topmost_timer is not None:
                self._topmost_timer.stop()

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
        self.title_panel.set_theme(self.theme)
        self.refresh()

    def set_icon_variant(self, variant: str):
        self.icon_variant = variant
        self.left_panel.set_icon_variant(variant)
        self.right_panel.set_icon_variant(variant)
        self.ffa_panel.set_icon_variant(variant)

    def set_title(self, title: str):
        self.title_panel.set_title(title)

    def set_title_visible(self, visible: bool):
        self.title_panel.setVisible(visible)

    def set_score_font_size(self, size: int):
        self.center_panel.set_score_font_size(size)

    def set_title_font_size(self, size: int):
        self.title_panel.set_title_font_size(size)

    def set_color_style(self, style: str):
        for panel in (self.left_panel, self.right_panel, self.ffa_panel):
            panel.set_color_style(style)

    def set_name_font_size(self, size: int):
        for panel in (self.left_panel, self.right_panel, self.ffa_panel):
            panel.set_name_font_size(size)
        # Ширина поля ніка залежить від метрик шрифту — перераховуємо.
        self._apply_name_widths()

    def set_elo_font_size(self, size: int):
        for panel in (self.left_panel, self.right_panel, self.ffa_panel):
            panel.set_elo_font_size(size)

    def set_row_spacing(self, spacing: int):
        for panel in (self.left_panel, self.right_panel, self.ffa_panel):
            panel.set_row_spacing(spacing)

    def set_panel_padding(self, padding: int):
        for panel in (self.left_panel, self.right_panel, self.ffa_panel):
            panel.set_vertical_padding(padding)

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

        self._apply_name_widths()

        # Перемикання team/FFA ховає/показує цілі панелі — інвалідація
        # скидає layout-кеш, а SetFixedSize на кореневому layout сам підганяє
        # вікно під новий вміст (переоцентрування — в resizeEvent).
        self.row_layout.invalidate()
        self.row_layout.activate()
        self.layout().invalidate()
        self.layout().activate()
        self.reposition()
        self._update_solid_mask()

    def _apply_name_widths(self):
        """Ширина поля ніка динамічна: підганяється під найдовший нік серед
        усіх гравців і однакова для всіх рядків — так обидві командні панелі
        мають рівну ширину, і рахунок лишається строго по центру."""
        if self.state.ffa:
            rows = self.ffa_panel.rows
        else:
            rows = self.left_panel.rows + self.right_panel.rows
        if not rows:
            return
        metrics = QFontMetrics(rows[0].name_label.font())
        width = max(
            (metrics.horizontalAdvance(p.name or "—") for p in self.state.players),
            default=0,
        )
        for row in rows:
            row.set_name_width(width + 8)

    def set_position(self, position_key: str):
        self.position_key = position_key
        self.reposition()

    def set_screen_index(self, index: int):
        """Монітор, на якому показується оверлей (0 = перший). Працює і на
        Windows, і на macOS — список екранів дає Qt."""
        self.screen_index = index
        self.reposition()

    def _target_screen(self):
        screens = QApplication.screens()
        if 0 <= self.screen_index < len(screens):
            return screens[self.screen_index]
        return QApplication.primaryScreen()

    def set_solid_background(self, enabled: bool, color: str | None = None):
        """Режим сумісності захоплення: замість прозорого layered-вікна —
        звичайне вікно з суцільним фоном. Старі методи захоплення OBS
        (BitBlt) не вміють знімати напівпрозорі вікна Windows; суцільний
        зелений/магента фон легко вирізається хромакеєм у сцені."""
        if color is not None:
            self._solid_bg_color = color
        if enabled == self._solid_bg and color is None:
            return
        need_recreate = enabled != self._solid_bg
        self._solid_bg = enabled
        if need_recreate:
            # Зміна WA_TranslucentBackground вимагає перестворення нативного
            # вікна — робимо це через повторне встановлення прапорців.
            was_visible = self.isVisible()
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, not enabled)
            self.setWindowFlags(self._window_flags())
            if was_visible:
                self.show()
            self.reposition()
        self._update_solid_mask()
        self.update()

    def _update_solid_mask(self):
        """У режимі суцільного фону вікну надається маска за формою панелей
        скорбару (включно зі зрізаними кутами) — фон не вилазить за межі
        скорбару, а сумісність із BitBlt зберігається, бо маска не потребує
        альфа-каналу. У звичайному (прозорому) режимі маска знімається."""
        if not self._solid_bg:
            self.clearMask()
            return
        region = QRegion()
        if self.state.ffa:
            panels = [self.ffa_panel]
        else:
            panels = [self.left_panel, self.center_panel, self.right_panel]
        panels.append(self.title_panel)
        for panel in panels:
            if not panel.isVisible():
                continue
            w, h = panel.width(), panel.height()
            n = max(min(panel.theme.notch, w // 4, h // 4), 0)
            poly = panel._panel_path(w, h, n).toFillPolygon().toPolygon()
            offset = panel.mapTo(self, QPoint(0, 0))
            poly.translate(offset.x(), offset.y())
            region = region.united(QRegion(poly))
        self.setMask(region)

    def set_glow_enabled(self, enabled: bool):
        for panel in (
            self.left_panel,
            self.center_panel,
            self.right_panel,
            self.ffa_panel,
            self.title_panel,
        ):
            panel.set_glow_enabled(enabled)

    def paintEvent(self, event):
        if self._solid_bg:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(self._solid_bg_color))
            painter.end()
        super().paintEvent(event)

    def resizeEvent(self, event):
        """Розмір вікна змінюється асинхронно (layout-події Qt приходять
        після refresh/reposition), тому центруємо вікно заново після кожної
        фактичної зміни розміру — інакше вікно доростає вправо від старого
        лівого краю і центральна панель з'їжджає з центру екрана."""
        super().resizeEvent(event)
        self.reposition()
        # Форма/розташування панелей могли змінитись — маска суцільного
        # фону перераховується під нову геометрію.
        self._update_solid_mask()

    def reposition(self, margin: int = 6):
        screen = self._target_screen()
        if not screen:
            return
        geo = screen.availableGeometry()
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
