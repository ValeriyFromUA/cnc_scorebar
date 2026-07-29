"""Окрема панель керування скорбаром: режими, гравці, фракції, прапори,
теми, позиція оверлею, збереження/завантаження конфігурації.

Додаток не реагує на клавіатуру взагалі: жодних гарячих клавіш немає,
з клавіатурою працює лише ця панель (текстові поля імені/карти/назви),
а всі числові поля (рахунок, розмір команди, кількість гравців) — лише
через кнопки інтерфейсу (+/- або стрілки спінбокса), без прямого вводу
з клавіатури.

Поточний стан автоматично зберігається у CONFIG_PATH після кожної зміни
(autosave) і підвантажується звідти при старті (autoload) — тож при
повторному відкритті панелі/оверлею все виглядає так само, як було до
закриття.

Запуск: python control_panel.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

from PyQt6.QtCore import QObject, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QIntValidator,
    QPainter,
    QPen,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from data import COUNTRIES, FACTIONS, PLAYER_COLORS, FactionGroup, MatchState, Player
from themes import THEMES, control_panel_qss, get_default_icon_variant, get_theme
from scorebar import ScorebarWindow

ICON_VARIANT_LABELS = {
    "blue": "Синя",
    "orng": "Оранжева",
    "slvr": "Срібна",
}

COLOR_STYLE_LABELS = {
    "triangle": "Трикутник",
    "underline": "Лінія під ніком",
    "edge": "Зафарбований край",
}


def _default_config_path() -> str:
    """Конфіг лежить поруч з exe/скриптом (а не в поточній робочій теці —
    на Windows ярлик може мати будь-який "робочий каталог", і конфіг
    "губився" б). Якщо тека не доступна на запис (напр. Program Files) —
    фолбек у %APPDATA%/Scorebar (на інших системах ~/.config/scorebar)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    path = base / "scorebar_config.json"
    try:
        if path.exists():
            with open(path, "r+", encoding="utf-8"):
                pass
        else:
            path.touch()
            path.unlink()
        return str(path)
    except OSError:
        if sys.platform.startswith("win"):
            config_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "Scorebar"
        else:
            config_dir = Path.home() / ".config" / "scorebar"
        config_dir.mkdir(parents=True, exist_ok=True)
        return str(config_dir / "scorebar_config.json")


CONFIG_PATH = _default_config_path()

SOLID_BG_COLORS = {
    "black": ("Чорний", "#000000"),
    "green": ("Зелений (хромакей)", "#00FF00"),
    "magenta": ("Магента (хромакей)", "#FF00FF"),
}

POSITION_LABELS = {
    "top_center": "Зверху по центру",
    "left_middle": "Зліва по середині",
    "right_middle": "Праворуч по середині",
}

REMOTE_PLAYERS_API_URL = "https://www.cnc-general-ukraine.org/api/players_elo/"


class RemotePlayersFetchWorker(QObject):
    """Тягне список гравців (дивізіон + ELO) з cnc-general-ukraine.org у
    фоновому потоці, щоб не блокувати UI панелі при старті."""

    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            with urllib.request.urlopen(REMOTE_PLAYERS_API_URL, timeout=8) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(data.get("players", []))


def _button_only_spin(spin: QSpinBox):
    """Забороняє прямий ввід цифр з клавіатури — значення міняється лише
    кнопками (стрілками спінбокса або сусідніми +/- кнопками)."""
    spin.setReadOnly(True)
    spin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)


def _build_stepper_row(label: str, minimum: int, maximum: int, value: int) -> tuple[QHBoxLayout, QSpinBox]:
    """Рядок "мінус / число / плюс" — зміна значення лише кнопками, в межах
    [minimum, maximum]."""
    row = QHBoxLayout()
    row.addWidget(QLabel(label))

    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setValue(value)
    _button_only_spin(spin)

    minus_btn = QPushButton("-")
    minus_btn.setFixedWidth(24)
    plus_btn = QPushButton("+")
    plus_btn.setFixedWidth(24)
    minus_btn.clicked.connect(lambda: spin.setValue(max(minimum, spin.value() - 1)))
    plus_btn.clicked.connect(lambda: spin.setValue(min(maximum, spin.value() + 1)))

    row.addWidget(minus_btn)
    row.addWidget(spin)
    row.addWidget(plus_btn)
    return row, spin


# --------------------------------------------------------------------------
# Допоміжні фабрики комбобоксів
# --------------------------------------------------------------------------

def build_country_combo() -> QComboBox:
    combo = QComboBox()
    combo.setIconSize(QSize(20, 14))
    for country in COUNTRIES:
        pixmap = QPixmap(str(country.flag_path))
        icon = QIcon(pixmap) if not pixmap.isNull() else QIcon()
        combo.addItem(icon, country.name, country.code)
    return combo


def build_faction_combo() -> QComboBox:
    combo = QComboBox()
    model = QStandardItemModel(combo)
    for group in (FactionGroup.USA, FactionGroup.CHINA, FactionGroup.GLA):
        header = QStandardItem(f"— {group.value} —")
        header.setFlags(Qt.ItemFlag.NoItemFlags)
        model.appendRow(header)
        for faction in FACTIONS:
            if faction.group is group:
                item = QStandardItem(faction.name)
                item.setData(faction.key, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
    combo.setModel(model)
    return combo


def build_color_combo() -> QComboBox:
    """Комбобокс кольору гравця без тексту — лише квадратики кольору
    (назва кольору в тултіпі), щоб рядок гравця був вужчим."""
    combo = QComboBox()
    combo.setIconSize(QSize(18, 18))

    # "Без кольору" — перекреслений квадратик.
    none_pixmap = QPixmap(18, 18)
    none_pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(none_pixmap)
    painter.setPen(QPen(QColor("#7A7A7A")))
    painter.drawRect(0, 0, 17, 17)
    painter.drawLine(1, 16, 16, 1)
    painter.end()
    combo.addItem(QIcon(none_pixmap), "", None)
    combo.setItemData(0, "Без кольору", Qt.ItemDataRole.ToolTipRole)

    for key, label, hex_color in PLAYER_COLORS:
        pixmap = QPixmap(18, 18)
        pixmap.fill(QColor(hex_color))
        combo.addItem(QIcon(pixmap), "", key)
        combo.setItemData(combo.count() - 1, label, Qt.ItemDataRole.ToolTipRole)

    combo.setFixedWidth(52)
    return combo


def combo_set_data(combo: QComboBox, value: str):
    idx = combo.findData(value)
    if idx < 0:
        # для faction-комбобокса дані лежать у UserRole кожного QStandardItem
        model = combo.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == value:
                idx = row
                break
    if idx >= 0:
        combo.setCurrentIndex(idx)


def combo_get_data(combo: QComboBox) -> str:
    data = combo.currentData()
    if data is not None:
        return data
    model = combo.model()
    item = model.item(combo.currentIndex())
    if item:
        return item.data(Qt.ItemDataRole.UserRole)
    return ""


# --------------------------------------------------------------------------
# Рядок редагування гравця
# --------------------------------------------------------------------------

class PlayerEditRow(QWidget):
    """Рядок редагування гравця.

    fixed_team=None  -> FFA-режим, команда не застосовується (завжди 0).
    fixed_team=0/1   -> командний режим; команда визначається колонкою,
                        у якій лежить рядок, тому окремий комбобокс команди
                        не потрібен.

    show_score керує особистим рахунком гравця: у FFA він потрібен (за ним
    рахується ранг), а в командному режимі рахунок — один на команду
    (керується окремими полями над колонкою), тому особистий рахунок
    гравця тут не показуємо, щоб не плутати з командним.
    """

    changed = pyqtSignal()

    def __init__(self, fixed_team: int | None, show_score: bool = True, parent=None):
        super().__init__(parent)
        self.fixed_team = fixed_team
        self.show_score = show_score
        self._division: str | None = None
        self._elo: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Вибір гравця зі списку cnc-general-ukraine.org (дивізіон + ELO
        # підставляються автоматично) або "Вручну" — тоді ім'я вводиться
        # текстовим полем нижче як завжди.
        # Без фіксованих максимальних ширин: поля еластичні (stretch-фактори
        # при додаванні в layout нижче), тож рядок розтягується разом з вікном.
        self.player_combo = QComboBox()
        self.player_combo.addItem("— Вручну —", None)
        self.name_edit = QLineEdit("Player")
        # Ручний ввід ELO: порожнє поле = використовується скачане з сайту
        # значення (воно видно в плейсхолдері), введене число перебиває його.
        # Це звичайне текстове поле панелі керування — фокус отримує лише по
        # кліку в самій панелі, глобального перехоплення клавіатури немає,
        # тож ввід в інших вікнах не блокується.
        self.elo_edit = QLineEdit()
        self.elo_edit.setPlaceholderText("ELO")
        self.elo_edit.setValidator(QIntValidator(0, 9999, self))
        self.elo_edit.setMaximumWidth(64)
        self.country_combo = build_country_combo()
        self.faction_combo = build_faction_combo()
        self.color_combo = build_color_combo()

        self.score_spin = QSpinBox()
        self.score_spin.setRange(0, 999)
        _button_only_spin(self.score_spin)

        minus_btn = QPushButton("-")
        minus_btn.setFixedWidth(24)
        plus_btn = QPushButton("+")
        plus_btn.setFixedWidth(24)
        minus_btn.clicked.connect(lambda: self.score_spin.setValue(max(0, self.score_spin.value() - 1)))
        plus_btn.clicked.connect(lambda: self.score_spin.setValue(self.score_spin.value() + 1))

        layout.addWidget(self.player_combo, 2)
        layout.addWidget(self.name_edit, 2)
        layout.addWidget(self.elo_edit)
        layout.addWidget(self.country_combo, 2)
        layout.addWidget(self.faction_combo, 2)
        layout.addWidget(self.color_combo)
        if show_score:
            layout.addWidget(minus_btn)
            layout.addWidget(self.score_spin)
            layout.addWidget(plus_btn)

        self.player_combo.currentIndexChanged.connect(self.on_player_combo_changed)
        self.name_edit.textChanged.connect(self.changed.emit)
        self.elo_edit.textChanged.connect(self.changed.emit)
        self.country_combo.currentIndexChanged.connect(self.changed.emit)
        self.faction_combo.currentIndexChanged.connect(self.changed.emit)
        self.color_combo.currentIndexChanged.connect(self.changed.emit)
        self.score_spin.valueChanged.connect(self.changed.emit)

    def set_remote_players(self, players: list[dict]):
        """Заповнює спадний список гравцями, отриманими з API
        cnc-general-ukraine.org (нікнейм, дивізіон, ELO)."""
        current_data = self.player_combo.currentData()
        self.player_combo.blockSignals(True)
        self.player_combo.clear()
        self.player_combo.addItem("— Вручну —", None)
        # У списку показуємо лише нік — дивізіон і ELO все одно
        # підтягуються в дані гравця при виборі.
        for p in players:
            self.player_combo.addItem(p.get("nickname") or "?", p)
        if current_data:
            for i in range(self.player_combo.count()):
                if self.player_combo.itemData(i) == current_data:
                    self.player_combo.setCurrentIndex(i)
                    break
        self.player_combo.blockSignals(False)

    def on_player_combo_changed(self, index: int):
        data = self.player_combo.itemData(index)
        if not data:
            self._division = None
            self._elo = None
            self.elo_edit.setPlaceholderText("ELO")
            return
        self.name_edit.setText(data.get("nickname") or self.name_edit.text())
        self._division = data.get("division")
        self._elo = data.get("elo")
        # Вибір іншого гравця скидає ручний override — інакше на скорбарі
        # лишилось би вручну введене ELO попереднього гравця.
        self.elo_edit.clear()
        self.elo_edit.setPlaceholderText(str(self._elo) if self._elo is not None else "ELO")
        self.changed.emit()

    def to_player(self) -> Player:
        manual_elo = self.elo_edit.text().strip()
        return Player(
            name=self.name_edit.text().strip() or "Player",
            country_code=combo_get_data(self.country_combo) or "UA",
            faction_key=combo_get_data(self.faction_combo) or "usa",
            team=self.fixed_team if self.fixed_team is not None else 0,
            score=self.score_spin.value() if self.show_score else 0,
            division=self._division,
            elo=int(manual_elo) if manual_elo else self._elo,
            color_key=combo_get_data(self.color_combo),
        )

    def load_player(self, player: Player):
        self.name_edit.setText(player.name)
        combo_set_data(self.country_combo, player.country_code)
        combo_set_data(self.faction_combo, player.faction_key)
        combo_set_data(self.color_combo, player.color_key)
        self._division = player.division
        # Збережене ELO (скачане або колись введене вручну) стає базовим
        # значенням; поле ручного вводу лишається порожнім.
        self._elo = player.elo
        self.elo_edit.clear()
        self.elo_edit.setPlaceholderText(str(player.elo) if player.elo is not None else "ELO")
        if self.show_score:
            self.score_spin.setValue(player.score)


# --------------------------------------------------------------------------
# Головне вікно панелі керування
# --------------------------------------------------------------------------

class ControlPanel(QWidget):
    def __init__(self, scorebar: ScorebarWindow):
        super().__init__()
        self.scorebar = scorebar
        self.setWindowTitle("Scorebar — панель керування")
        self.resize(560, 640)

        self.player_rows: list[PlayerEditRow] = []
        self.remote_players: list[dict] = []
        # Поки йде початкове налаштування (rebuild_players/autoload), autosave
        # вимкнено — інакше дефолтні значення UI перезаписали б щойно
        # завантажений з диска стан ще до того, як autoload встигне його
        # застосувати.
        self._suspend_autosave = True

        root = QVBoxLayout(self)

        # Дві вкладки: "Гра" — все про матч (режим, гравці, рахунок),
        # "Дизайн" — все про вигляд і розміщення оверлею.
        self.tabs = QTabWidget()

        game_tab = QWidget()
        game_layout = QVBoxLayout(game_tab)
        game_layout.addWidget(self._build_mode_group())
        # Блок гравців забирає весь вільний простір — панель росте/стискається
        # разом із вікном, а не лишає порожнє місце під собою.
        game_layout.addWidget(self._build_players_group(), 1)
        game_layout.addWidget(self._build_actions_group())

        design_tab = QWidget()
        design_layout = QVBoxLayout(design_tab)
        design_layout.addWidget(self._build_theme_group())
        design_layout.addWidget(self._build_font_group())
        design_layout.addWidget(self._build_spacing_group())
        design_layout.addWidget(self._build_position_group())
        design_layout.addWidget(self._build_monitor_group())
        design_layout.addStretch(1)

        compat_tab = QWidget()
        compat_layout = QVBoxLayout(compat_tab)
        compat_layout.addWidget(self._build_capture_group())
        compat_layout.addWidget(self._build_effects_group())
        compat_layout.addStretch(1)

        self.tabs.addTab(game_tab, "Гра")
        self.tabs.addTab(design_tab, "Дизайн")
        self.tabs.addTab(compat_tab, "Сумісність")

        root.addWidget(self.tabs)
        root.addWidget(self._build_footer())

        self.apply_theme_qss()
        self.rebuild_players()
        self.autoload()
        self._suspend_autosave = False

        self.fetch_remote_players()

    def closeEvent(self, event):
        # Оверлей без панелі керування нікому не потрібен — закриваємо його
        # разом із панеллю, а не лишаємо висіти окремим процесом/вікном.
        self.scorebar.close()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    def fetch_remote_players(self):
        """Підвантажує список гравців (дивізіон + ELO) з
        cnc-general-ukraine.org у фоновому потоці, щоб не блокувати UI."""
        self._players_thread = QThread(self)
        self._players_worker = RemotePlayersFetchWorker()
        self._players_worker.moveToThread(self._players_thread)
        self._players_thread.started.connect(self._players_worker.run)
        self._players_worker.finished.connect(self.on_remote_players_loaded)
        self._players_worker.failed.connect(self.on_remote_players_failed)
        self._players_worker.finished.connect(self._players_thread.quit)
        self._players_worker.failed.connect(self._players_thread.quit)
        self._players_thread.start()

    def on_remote_players_loaded(self, players: list):
        self.remote_players = players
        for row in self.player_rows:
            row.set_remote_players(players)

    def on_remote_players_failed(self, error: str):
        # Список гравців із сайту недоступний — мовчки лишаємо лише ручний
        # ввід, без спливаючих помилок (це не критичний функціонал).
        pass

    # ------------------------------------------------------------------
    def _build_mode_group(self) -> QGroupBox:
        box = QGroupBox("Режим матчу")
        layout = QVBoxLayout(box)

        mode_row = QHBoxLayout()
        self.radio_team = QRadioButton("Командний (1v1 .. 4v4)")
        self.radio_ffa = QRadioButton("FFA")
        self.radio_team.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.radio_team)
        group.addButton(self.radio_ffa)
        self.radio_team.toggled.connect(self.rebuild_players)
        mode_row.addWidget(self.radio_team)
        mode_row.addWidget(self.radio_ffa)
        layout.addLayout(mode_row)

        size_row = QHBoxLayout()
        team_size_row, self.team_size_spin = _build_stepper_row("Розмір команди:", 1, 4, 1)
        self.team_size_spin.valueChanged.connect(self.rebuild_players)
        size_row.addLayout(team_size_row)

        ffa_count_row, self.ffa_count_spin = _build_stepper_row("Гравців у FFA:", 2, 8, 4)
        self.ffa_count_spin.valueChanged.connect(self.rebuild_players)
        size_row.addLayout(ffa_count_row)
        layout.addLayout(size_row)

        map_row = QHBoxLayout()
        map_row.addWidget(QLabel("Карта:"))
        self.map_edit = QLineEdit()
        self.map_edit.textChanged.connect(self.push_state)
        map_row.addWidget(self.map_edit)
        layout.addLayout(map_row)

        return box

    def _build_theme_group(self) -> QGroupBox:
        box = QGroupBox("Оформлення")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme.name, key)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        row1.addWidget(self.theme_combo)

        row1.addWidget(QLabel("Іконка генерала:"))
        self.icon_variant_combo = QComboBox()
        for variant, label in ICON_VARIANT_LABELS.items():
            self.icon_variant_combo.addItem(label, variant)
        self.icon_variant_combo.currentIndexChanged.connect(self.on_icon_variant_changed)
        row1.addWidget(self.icon_variant_combo)

        row1.addWidget(QLabel("Маркер кольору:"))
        self.color_style_combo = QComboBox()
        for key, label in COLOR_STYLE_LABELS.items():
            self.color_style_combo.addItem(label, key)
        self.color_style_combo.currentIndexChanged.connect(self.on_color_style_changed)
        row1.addWidget(self.color_style_combo)
        row1.addStretch(1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Заголовок:"))
        self.title_edit = QLineEdit("SCOREBAR")
        self.title_edit.setMaximumWidth(120)
        self.title_edit.textChanged.connect(self.on_title_changed)
        row2.addWidget(self.title_edit)

        self.show_title_check = QCheckBox("Показувати заголовок")
        self.show_title_check.setChecked(True)
        self.show_title_check.toggled.connect(self.on_show_title_changed)
        row2.addWidget(self.show_title_check)

        self.always_on_top_check = QCheckBox("Поверх усіх вікон")
        self.always_on_top_check.setToolTip(
            "Тримає оверлей над усіма вікнами, включно з грою у віконному/borderless режимі.\n"
            "Для захоплення в OBS не потрібно — OBS сам розміщує джерело в сцені.\n"
            "Поверх гри в ексклюзивному повноекранному режимі не працює (обмеження системи)."
        )
        self.always_on_top_check.toggled.connect(self.on_always_on_top_changed)
        row2.addWidget(self.always_on_top_check)
        row2.addStretch(1)
        layout.addLayout(row2)

        return box

    def _build_position_group(self) -> QGroupBox:
        box = QGroupBox("Позиція оверлею")
        layout = QHBoxLayout(box)

        self.position_radios: dict[str, QRadioButton] = {}
        group = QButtonGroup(self)
        for key, label in POSITION_LABELS.items():
            radio = QRadioButton(label)
            group.addButton(radio)
            layout.addWidget(radio)
            self.position_radios[key] = radio
        self.position_radios["top_center"].setChecked(True)
        self.position_button_group = group
        group.buttonToggled.connect(self.on_position_changed)

        return box

    def on_position_changed(self, button: QRadioButton, checked: bool):
        if not checked:
            return
        for key, radio in self.position_radios.items():
            if radio is button:
                self.scorebar.set_position(key)
                self.autosave()
                break

    def _build_font_group(self) -> QGroupBox:
        box = QGroupBox("Шрифти")
        layout = QHBoxLayout(box)

        score_row, self.score_font_spin = _build_stepper_row("Рахунок:", 10, 48, 20)
        self.score_font_spin.valueChanged.connect(self.on_score_font_changed)
        layout.addLayout(score_row)

        name_row, self.name_font_spin = _build_stepper_row("Ніки:", 8, 24, 11)
        self.name_font_spin.valueChanged.connect(self.on_name_font_changed)
        layout.addLayout(name_row)

        title_row, self.title_font_spin = _build_stepper_row("Заголовок:", 8, 36, 11)
        self.title_font_spin.valueChanged.connect(self.on_title_font_changed)
        layout.addLayout(title_row)

        elo_row, self.elo_font_spin = _build_stepper_row("ELO:", 8, 24, 13)
        self.elo_font_spin.valueChanged.connect(self.on_elo_font_changed)
        layout.addLayout(elo_row)
        layout.addStretch(1)
        return box

    def _build_spacing_group(self) -> QGroupBox:
        box = QGroupBox("Відступи")
        layout = QHBoxLayout(box)

        spacing_row, self.row_spacing_spin = _build_stepper_row("Між ніками:", 0, 16, 4)
        self.row_spacing_spin.valueChanged.connect(self.on_row_spacing_changed)
        layout.addLayout(spacing_row)

        padding_row, self.panel_padding_spin = _build_stepper_row("Рамка до ніків:", 0, 20, 6)
        self.panel_padding_spin.valueChanged.connect(self.on_panel_padding_changed)
        layout.addLayout(padding_row)
        layout.addStretch(1)
        return box

    def on_score_font_changed(self, value: int):
        self.scorebar.set_score_font_size(value)
        self.autosave()

    def on_name_font_changed(self, value: int):
        self.scorebar.set_name_font_size(value)
        self.autosave()

    def on_title_font_changed(self, value: int):
        self.scorebar.set_title_font_size(value)
        self.autosave()

    def on_elo_font_changed(self, value: int):
        self.scorebar.set_elo_font_size(value)
        self.autosave()

    def on_color_style_changed(self):
        self.scorebar.set_color_style(self.color_style_combo.currentData())
        self.autosave()

    def on_row_spacing_changed(self, value: int):
        self.scorebar.set_row_spacing(value)
        self.autosave()

    def on_panel_padding_changed(self, value: int):
        self.scorebar.set_panel_padding(value)
        self.autosave()

    def _build_capture_group(self) -> QGroupBox:
        box = QGroupBox("Захоплення (OBS)")
        layout = QVBoxLayout(box)

        self.solid_bg_check = QCheckBox("Суцільний фон замість прозорого")
        self.solid_bg_check.setToolTip(
            "Режим сумісності для старих методів захоплення (BitBlt), які не\n"
            "вміють знімати напівпрозорі вікна Windows. Зелений/магента фон\n"
            "вирізається в OBS фільтром Chroma Key.\n"
            "Після перемикання вікно перестворюється — можливо, доведеться\n"
            "перевибрати його в джерелі Window Capture."
        )
        self.solid_bg_check.toggled.connect(self.on_solid_bg_changed)
        layout.addWidget(self.solid_bg_check)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Колір фону:"))
        self.solid_bg_color_combo = QComboBox()
        for key, (label, _hex) in SOLID_BG_COLORS.items():
            self.solid_bg_color_combo.addItem(label, key)
        self.solid_bg_color_combo.currentIndexChanged.connect(self.on_solid_bg_changed)
        color_row.addWidget(self.solid_bg_color_combo)
        color_row.addStretch(1)
        layout.addLayout(color_row)

        return box

    def _build_effects_group(self) -> QGroupBox:
        box = QGroupBox("Ефекти")
        layout = QVBoxLayout(box)

        self.disable_glow_check = QCheckBox("Вимкнути світіння (тіні/glow)")
        self.disable_glow_check.setToolTip(
            "Неонові теми використовують ефект світіння навколо панелей.\n"
            "На слабших машинах або при захопленні він інколи дає артефакти\n"
            "чи просідання FPS — цей перемикач повністю його вимикає."
        )
        self.disable_glow_check.toggled.connect(self.on_disable_glow_changed)
        layout.addWidget(self.disable_glow_check)

        return box

    def on_solid_bg_changed(self):
        color_key = self.solid_bg_color_combo.currentData()
        color_hex = SOLID_BG_COLORS.get(color_key, SOLID_BG_COLORS["black"])[1]
        self.scorebar.set_solid_background(self.solid_bg_check.isChecked(), color_hex)
        self.autosave()

    def on_disable_glow_changed(self, checked: bool):
        self.scorebar.set_glow_enabled(not checked)
        self.autosave()

    def _build_monitor_group(self) -> QGroupBox:
        box = QGroupBox("Монітор")
        layout = QHBoxLayout(box)

        layout.addWidget(QLabel("Екран оверлею:"))
        self.monitor_combo = QComboBox()
        self._populate_monitor_combo()
        self.monitor_combo.currentIndexChanged.connect(self.on_monitor_changed)
        layout.addWidget(self.monitor_combo)
        layout.addStretch(1)

        # Список екранів живий: підключення/відключення монітора під час
        # роботи оновлює комбобокс автоматично.
        app = QApplication.instance()
        app.screenAdded.connect(self._on_screens_changed)
        app.screenRemoved.connect(self._on_screens_changed)
        return box

    def _populate_monitor_combo(self):
        current = self.monitor_combo.currentData()
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        for i, screen in enumerate(QApplication.screens()):
            geo = screen.geometry()
            self.monitor_combo.addItem(f"Монітор {i + 1} ({geo.width()}×{geo.height()})", i)
        if current is not None:
            idx = self.monitor_combo.findData(current)
            if idx >= 0:
                self.monitor_combo.setCurrentIndex(idx)
        self.monitor_combo.blockSignals(False)

    def _on_screens_changed(self, _screen):
        self._populate_monitor_combo()
        self.on_monitor_changed()

    def on_monitor_changed(self):
        index = self.monitor_combo.currentData()
        self.scorebar.set_screen_index(index if index is not None else 0)
        self.autosave()

    def _build_players_group(self) -> QGroupBox:
        box = QGroupBox("Гравці")
        outer = QVBoxLayout(box)
        self.players_scroll = QScrollArea()
        self.players_scroll.setWidgetResizable(True)
        self.players_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Горизонтального скролу немає: рядки гравців розтягуються рівно на
        # ширину вікна (поля рядка мають еластичну ширину).
        self.players_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.players_scroll.setMinimumHeight(160)
        self.players_container = QWidget()
        container_layout = QVBoxLayout(self.players_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Командний режим: команди одна під одною (Команда A, нижче Команда B),
        # щоб панель займала таку саму ширину, як і в FFA-режимі.
        self.teams_widget = QWidget()
        teams_col = QVBoxLayout(self.teams_widget)
        teams_col.setContentsMargins(0, 0, 0, 0)

        team_a_box = QVBoxLayout()
        team_a_label = QLabel("Команда A")
        team_a_label.setObjectName("sectionTitle")
        team_a_box.addWidget(team_a_label)
        self.team_a_score_spin = self._build_team_score_row(team_a_box, "a")
        self.team_a_layout = QVBoxLayout()
        self.team_a_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.team_a_layout.setSpacing(4)
        team_a_box.addLayout(self.team_a_layout)

        team_b_box = QVBoxLayout()
        team_b_label = QLabel("Команда B")
        team_b_label.setObjectName("sectionTitle")
        team_b_box.addWidget(team_b_label)
        self.team_b_score_spin = self._build_team_score_row(team_b_box, "b")
        self.team_b_layout = QVBoxLayout()
        self.team_b_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.team_b_layout.setSpacing(4)
        team_b_box.addLayout(self.team_b_layout)

        teams_col.addLayout(team_a_box)
        teams_col.addLayout(team_b_box)

        # FFA режим: один список без колонок.
        self.ffa_widget = QWidget()
        ffa_outer = QVBoxLayout(self.ffa_widget)
        ffa_outer.setContentsMargins(0, 0, 0, 0)
        self.ffa_layout = QVBoxLayout()
        self.ffa_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ffa_layout.setSpacing(4)
        ffa_outer.addLayout(self.ffa_layout)

        container_layout.addWidget(self.teams_widget)
        container_layout.addWidget(self.ffa_widget)
        # Розпірка притискає списки догори, коли скрол-зона вища за вміст.
        container_layout.addStretch(1)

        self.players_scroll.setWidget(self.players_container)
        outer.addWidget(self.players_scroll)
        return box

    def _build_team_score_row(self, parent_layout: QVBoxLayout, side: str) -> QSpinBox:
        """Один рахунок на всю команду (а не на кожного гравця окремо)."""
        row = QHBoxLayout()
        row.addWidget(QLabel("Рахунок:"))

        spin = QSpinBox()
        spin.setRange(0, 999)
        _button_only_spin(spin)

        minus_btn = QPushButton("-")
        minus_btn.setFixedWidth(24)
        plus_btn = QPushButton("+")
        plus_btn.setFixedWidth(24)
        minus_btn.clicked.connect(lambda: spin.setValue(max(0, spin.value() - 1)))
        plus_btn.clicked.connect(lambda: spin.setValue(spin.value() + 1))
        spin.valueChanged.connect(lambda value: self.set_team_score(side, value))

        row.addWidget(minus_btn)
        row.addWidget(spin)
        row.addWidget(plus_btn)
        parent_layout.addLayout(row)
        return spin

    def set_team_score(self, side: str, value: int):
        if side == "a":
            self.scorebar.state.score_a = value
        else:
            self.scorebar.state.score_b = value
        self.scorebar.center_panel.update_state(self.scorebar.state)
        self.autosave()

    def _build_actions_group(self) -> QGroupBox:
        box = QGroupBox("Керування")
        layout = QHBoxLayout(box)

        toggle_btn = QPushButton("Показати/Сховати оверлей")
        toggle_btn.clicked.connect(self.scorebar.toggle_visibility)
        reset_btn = QPushButton("Скинути рахунок")
        reset_btn.clicked.connect(self.reset_scores)
        save_btn = QPushButton("Зберегти конфіг")
        save_btn.clicked.connect(self.save_config)
        load_btn = QPushButton("Завантажити конфіг")
        load_btn.clicked.connect(self.load_config)

        for w in (toggle_btn, reset_btn, save_btn, load_btn):
            layout.addWidget(w)
        return box

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        made_label = QLabel("Зроблено в Україні — FROM_UA 🇺🇦")
        made_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        made_label.setObjectName("footerLabel")

        slava_label = QLabel("СЛАВА УКРАЇНІ — і нехай горить москва 🔥")
        slava_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slava_label.setObjectName("footerLabel")

        layout.addWidget(made_label)
        layout.addWidget(slava_label)
        return footer

    # ------------------------------------------------------------------
    def rebuild_players(self):
        is_team = self.radio_team.isChecked()
        self.team_size_spin.setEnabled(is_team)
        self.ffa_count_spin.setEnabled(not is_team)
        self.teams_widget.setVisible(is_team)
        self.ffa_widget.setVisible(not is_team)

        self.team_a_score_spin.blockSignals(True)
        self.team_b_score_spin.blockSignals(True)
        self.team_a_score_spin.setValue(self.scorebar.state.score_a)
        self.team_b_score_spin.setValue(self.scorebar.state.score_b)
        self.team_a_score_spin.blockSignals(False)
        self.team_b_score_spin.blockSignals(False)

        old_players = [row.to_player() for row in self.player_rows]

        for row in self.player_rows:
            self.team_a_layout.removeWidget(row)
            self.team_b_layout.removeWidget(row)
            self.ffa_layout.removeWidget(row)
            row.deleteLater()
        self.player_rows.clear()

        if is_team:
            n = self.team_size_spin.value()
            for i in range(n):
                # Колонка "Команда A": гравці 0..n-1.
                row = PlayerEditRow(fixed_team=0, show_score=False)
                if i < len(old_players):
                    row.load_player(old_players[i])
                else:
                    row.load_player(Player(name=f"Player {i + 1}", team=0))
                row.changed.connect(self.push_state)
                self.team_a_layout.addWidget(row)
                self.player_rows.append(row)
            for i in range(n):
                # Колонка "Команда B": гравці n..2n-1.
                row = PlayerEditRow(fixed_team=1, show_score=False)
                src_idx = n + i
                if src_idx < len(old_players):
                    row.load_player(old_players[src_idx])
                else:
                    row.load_player(Player(name=f"Player {n + i + 1}", team=1))
                row.changed.connect(self.push_state)
                self.team_b_layout.addWidget(row)
                self.player_rows.append(row)
        else:
            count = self.ffa_count_spin.value()
            for i in range(count):
                row = PlayerEditRow(fixed_team=None, show_score=True)
                if i < len(old_players):
                    row.load_player(old_players[i])
                else:
                    row.load_player(Player(name=f"Player {i + 1}"))
                row.changed.connect(self.push_state)
                self.ffa_layout.addWidget(row)
                self.player_rows.append(row)

        if self.remote_players:
            for row in self.player_rows:
                row.set_remote_players(self.remote_players)

        self.push_state()

    def push_state(self):
        is_team = self.radio_team.isChecked()
        players = [row.to_player() for row in self.player_rows]
        state = MatchState(
            ffa=not is_team,
            team_size=self.team_size_spin.value(),
            players=players,
            score_a=self.scorebar.state.score_a if hasattr(self.scorebar, "state") else 0,
            score_b=self.scorebar.state.score_b if hasattr(self.scorebar, "state") else 0,
            map_name=self.map_edit.text().strip(),
        )
        self.scorebar.set_match(state)
        self.autosave()

    def reset_scores(self):
        self.scorebar.state.score_a = 0
        self.scorebar.state.score_b = 0
        self.team_a_score_spin.setValue(0)
        self.team_b_score_spin.setValue(0)
        for row in self.player_rows:
            row.score_spin.setValue(0)
        self.push_state()

    # ------------------------------------------------------------------
    def on_theme_changed(self):
        key = self.theme_combo.currentData()
        self.scorebar.set_theme(key)
        self.apply_theme_qss()
        # Кожна тема має свій дефолтний колір іконки генерала — застосовуємо
        # його при зміні теми; після цього колір можна перемкнути вручну.
        idx = self.icon_variant_combo.findData(get_default_icon_variant(key))
        if idx >= 0:
            self.icon_variant_combo.setCurrentIndex(idx)
        self.autosave()

    def apply_theme_qss(self):
        theme = get_theme(self.theme_combo.currentData() or "cnc")
        self.setStyleSheet(control_panel_qss(theme))

    def on_icon_variant_changed(self):
        variant = self.icon_variant_combo.currentData()
        self.scorebar.set_icon_variant(variant)
        self.autosave()

    def on_always_on_top_changed(self, checked: bool):
        self.scorebar.set_always_on_top(checked)
        self.autosave()

    def on_title_changed(self, text: str):
        self.scorebar.set_title(text)
        self.autosave()

    def on_show_title_changed(self, checked: bool):
        self.scorebar.set_title_visible(checked)
        self.autosave()

    # ------------------------------------------------------------------
    def _build_config_dict(self) -> dict:
        return {
            "ffa": self.radio_ffa.isChecked(),
            "team_size": self.team_size_spin.value(),
            "ffa_count": self.ffa_count_spin.value(),
            "map_name": self.map_edit.text(),
            "theme": self.theme_combo.currentData(),
            "icon_variant": self.icon_variant_combo.currentData(),
            "always_on_top": self.always_on_top_check.isChecked(),
            "title": self.title_edit.text(),
            "show_title": self.show_title_check.isChecked(),
            "score_font_size": self.score_font_spin.value(),
            "name_font_size": self.name_font_spin.value(),
            "title_font_size": self.title_font_spin.value(),
            "elo_font_size": self.elo_font_spin.value(),
            "row_spacing": self.row_spacing_spin.value(),
            "panel_padding": self.panel_padding_spin.value(),
            "color_style": self.color_style_combo.currentData(),
            "solid_bg": self.solid_bg_check.isChecked(),
            "solid_bg_color": self.solid_bg_color_combo.currentData(),
            "disable_glow": self.disable_glow_check.isChecked(),
            "players": [asdict(row.to_player()) for row in self.player_rows],
            "score_a": self.scorebar.state.score_a,
            "score_b": self.scorebar.state.score_b,
            "position": self.scorebar.position_key,
            "monitor": self.scorebar.screen_index,
        }

    def _apply_config_dict(self, data: dict):
        self.radio_ffa.setChecked(bool(data.get("ffa", False)))
        self.radio_team.setChecked(not data.get("ffa", False))
        self.team_size_spin.setValue(data.get("team_size", 1))
        self.ffa_count_spin.setValue(data.get("ffa_count", 4))
        self.map_edit.setText(data.get("map_name", ""))

        theme_key = data.get("theme", "cnc")
        idx = self.theme_combo.findData(theme_key)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

        # Застосовується ПІСЛЯ вибору теми, бо зміна теми сама скидає колір
        # іконки на дефолтний для цієї теми — тут перекриваємо його
        # збереженим (можливо, вручну обраним) значенням, якщо воно є.
        icon_variant = data.get("icon_variant")
        if icon_variant:
            idx = self.icon_variant_combo.findData(icon_variant)
            if idx >= 0:
                self.icon_variant_combo.setCurrentIndex(idx)

        self.always_on_top_check.setChecked(bool(data.get("always_on_top", False)))

        self.title_edit.setText(data.get("title", "SCOREBAR"))

        show_title = bool(data.get("show_title", True))
        self.show_title_check.setChecked(show_title)
        self.scorebar.set_title_visible(show_title)

        self.score_font_spin.setValue(data.get("score_font_size", 20))
        self.name_font_spin.setValue(data.get("name_font_size", 11))
        self.title_font_spin.setValue(data.get("title_font_size", 11))
        self.elo_font_spin.setValue(data.get("elo_font_size", 13))
        self.row_spacing_spin.setValue(data.get("row_spacing", 4))
        self.panel_padding_spin.setValue(data.get("panel_padding", 6))

        color_style = data.get("color_style", "triangle")
        idx = self.color_style_combo.findData(color_style)
        if idx >= 0:
            self.color_style_combo.setCurrentIndex(idx)
        self.scorebar.set_color_style(color_style)

        bg_color_key = data.get("solid_bg_color", "black")
        idx = self.solid_bg_color_combo.findData(bg_color_key)
        if idx >= 0:
            self.solid_bg_color_combo.setCurrentIndex(idx)
        self.solid_bg_check.setChecked(bool(data.get("solid_bg", False)))
        self.on_solid_bg_changed()

        self.disable_glow_check.setChecked(bool(data.get("disable_glow", False)))
        self.scorebar.set_glow_enabled(not self.disable_glow_check.isChecked())

        self.scorebar.state.score_a = data.get("score_a", 0)
        self.scorebar.state.score_b = data.get("score_b", 0)

        position_key = data.get("position", "top_center")
        radio = self.position_radios.get(position_key)
        if radio:
            radio.setChecked(True)
        self.scorebar.set_position(position_key)

        # Якщо збереженого монітора вже немає (відключили), _target_screen
        # у самому оверлеї відкотиться на основний екран.
        monitor_index = data.get("monitor", 0)
        idx = self.monitor_combo.findData(monitor_index)
        if idx >= 0:
            self.monitor_combo.setCurrentIndex(idx)
        self.scorebar.set_screen_index(monitor_index)

        self.rebuild_players()
        players_data = data.get("players", [])
        for row, pdata in zip(self.player_rows, players_data):
            row.load_player(Player(**pdata))

        self.push_state()

    # ------------------------------------------------------------------
    def autosave(self):
        """Автоматично зберігає поточний стан у CONFIG_PATH після кожної
        зміни, щоб при повторному відкритті оверлею все було як до закриття."""
        if self._suspend_autosave:
            return
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._build_config_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def autoload(self):
        """Підвантажує збережений автозбереженням стан при старті панелі,
        якщо файл CONFIG_PATH існує."""
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        self._apply_config_dict(data)

    # ------------------------------------------------------------------
    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Зберегти конфіг", CONFIG_PATH, "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._build_config_dict(), f, ensure_ascii=False, indent=2)

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Завантажити конфіг", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            QMessageBox.warning(self, "Помилка", f"Не вдалося прочитати файл: {exc}")
            return
        self._apply_config_dict(data)
        self.autosave()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    scorebar = ScorebarWindow()
    scorebar.show()

    panel = ControlPanel(scorebar)
    panel.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
