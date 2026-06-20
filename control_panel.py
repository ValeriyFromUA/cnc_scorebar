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
import sys
from dataclasses import asdict

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QVBoxLayout,
    QWidget,
)

from data import COUNTRIES, FACTIONS, FactionGroup, MatchState, Player
from themes import THEMES, control_panel_qss, get_theme
from scorebar import ScorebarWindow


CONFIG_PATH = "scorebar_config.json"

POSITION_LABELS = {
    "top_center": "Зверху по центру",
    "left_middle": "Зліва по середині",
    "right_middle": "Праворуч по середині",
}


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
    for country in COUNTRIES:
        combo.addItem(f"{country.flag}  {country.name}", country.code)
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.name_edit = QLineEdit("Player")
        self.name_edit.setMaximumWidth(110)
        self.country_combo = build_country_combo()
        self.faction_combo = build_faction_combo()

        self.score_spin = QSpinBox()
        self.score_spin.setRange(0, 999)
        _button_only_spin(self.score_spin)

        minus_btn = QPushButton("-")
        minus_btn.setFixedWidth(24)
        plus_btn = QPushButton("+")
        plus_btn.setFixedWidth(24)
        minus_btn.clicked.connect(lambda: self.score_spin.setValue(max(0, self.score_spin.value() - 1)))
        plus_btn.clicked.connect(lambda: self.score_spin.setValue(self.score_spin.value() + 1))

        layout.addWidget(self.name_edit)
        layout.addWidget(self.country_combo)
        layout.addWidget(self.faction_combo)
        if show_score:
            layout.addWidget(minus_btn)
            layout.addWidget(self.score_spin)
            layout.addWidget(plus_btn)

        self.name_edit.textChanged.connect(self.changed.emit)
        self.country_combo.currentIndexChanged.connect(self.changed.emit)
        self.faction_combo.currentIndexChanged.connect(self.changed.emit)
        self.score_spin.valueChanged.connect(self.changed.emit)

    def to_player(self) -> Player:
        return Player(
            name=self.name_edit.text().strip() or "Player",
            country_code=combo_get_data(self.country_combo) or "UA",
            faction_key=combo_get_data(self.faction_combo) or "usa",
            team=self.fixed_team if self.fixed_team is not None else 0,
            score=self.score_spin.value() if self.show_score else 0,
        )

    def load_player(self, player: Player):
        self.name_edit.setText(player.name)
        combo_set_data(self.country_combo, player.country_code)
        combo_set_data(self.faction_combo, player.faction_key)
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
        # Поки йде початкове налаштування (rebuild_players/autoload), autosave
        # вимкнено — інакше дефолтні значення UI перезаписали б щойно
        # завантажений з диска стан ще до того, як autoload встигне його
        # застосувати.
        self._suspend_autosave = True

        root = QVBoxLayout(self)

        root.addWidget(self._build_mode_group())
        root.addWidget(self._build_theme_group())
        root.addWidget(self._build_position_group())
        root.addWidget(self._build_players_group())
        root.addWidget(self._build_actions_group())
        root.addWidget(self._build_footer())

        self.apply_theme_qss()
        self.rebuild_players()
        self.autoload()
        self._suspend_autosave = False

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
        layout = QHBoxLayout(box)

        layout.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        for key, theme in THEMES.items():
            self.theme_combo.addItem(theme.name, key)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        layout.addWidget(self.theme_combo)

        layout.addWidget(QLabel("Заголовок:"))
        self.title_edit = QLineEdit("SCOREBAR")
        self.title_edit.setMaximumWidth(120)
        self.title_edit.textChanged.connect(self.on_title_changed)
        layout.addWidget(self.title_edit)

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

    def _build_players_group(self) -> QGroupBox:
        box = QGroupBox("Гравці")
        outer = QVBoxLayout(box)
        self.players_scroll = QScrollArea()
        self.players_scroll.setWidgetResizable(True)
        self.players_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Горизонтальний скрол вимикаємо: ширину панелі підганяємо під реальний
        # вміст (нижче, в _apply_players_panel_size), інакше QScrollArea не
        # "просить" у вікна достатньої ширини й рядки виглядають зжатими.
        self.players_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.players_container = QWidget()
        container_layout = QVBoxLayout(self.players_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Командний режим: дві колонки (Команда A / Команда B), щоб список
        # гравців у панелі керування відповідав розташуванню в самому скорбарі.
        self.team_columns_widget = QWidget()
        columns_row = QHBoxLayout(self.team_columns_widget)
        columns_row.setContentsMargins(0, 0, 0, 0)

        team_a_box = QVBoxLayout()
        team_a_label = QLabel("Команда A")
        team_a_label.setObjectName("sectionTitle")
        team_a_box.addWidget(team_a_label)
        self.team_a_score_spin = self._build_team_score_row(team_a_box, "a")
        self.team_a_layout = QVBoxLayout()
        self.team_a_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.team_a_layout.setSpacing(4)
        team_a_box.addLayout(self.team_a_layout)
        team_a_box.addStretch(1)

        team_b_box = QVBoxLayout()
        team_b_label = QLabel("Команда B")
        team_b_label.setObjectName("sectionTitle")
        team_b_box.addWidget(team_b_label)
        self.team_b_score_spin = self._build_team_score_row(team_b_box, "b")
        self.team_b_layout = QVBoxLayout()
        self.team_b_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.team_b_layout.setSpacing(4)
        team_b_box.addLayout(self.team_b_layout)
        team_b_box.addStretch(1)

        columns_row.addLayout(team_a_box)
        columns_row.addLayout(team_b_box)

        # FFA режим: один список без колонок.
        self.ffa_widget = QWidget()
        ffa_outer = QVBoxLayout(self.ffa_widget)
        ffa_outer.setContentsMargins(0, 0, 0, 0)
        self.ffa_layout = QVBoxLayout()
        self.ffa_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ffa_layout.setSpacing(4)
        ffa_outer.addLayout(self.ffa_layout)

        container_layout.addWidget(self.team_columns_widget)
        container_layout.addWidget(self.ffa_widget)

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

    def _resize_players_panel(self):
        """Підлаштовує висоту панелі гравців під фактичну кількість рядків,
        а не розтягує її на весь вільний простір вікна.

        sizeHint() щойно створених/переставлених віджетів буває неточним,
        доки Qt не обробить накопичені layout-події. Тому розрахунок
        відкладаємо на QTimer.singleShot(0, ...) — він виконається одразу
        після поточного циклу подій, коли всі sizeHint вже коректні.
        Без цього висота (а разом з нею і ширина) панелі рахувались по
        застарілих/нульових значеннях, і рядки виглядали зжатими разом
        із появою зайвого горизонтального скролу.
        """
        QTimer.singleShot(0, self._apply_players_panel_size)

    def _apply_players_panel_size(self):
        if not self.player_rows:
            return
        is_team = self.radio_team.isChecked()
        content_widget = self.team_columns_widget if is_team else self.ffa_widget

        row_height = self.player_rows[0].sizeHint().height()
        max_visible_height = row_height * 6 + 40
        hint_height = content_widget.sizeHint().height()
        target_height = min(max(hint_height, row_height), max_visible_height)

        self.players_scroll.setMinimumHeight(target_height)
        self.players_scroll.setMaximumHeight(target_height)
        self.players_scroll.setMinimumWidth(content_widget.sizeHint().width() + 4)
        self.adjustSize()

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
        self.team_columns_widget.setVisible(is_team)
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

        self._resize_players_panel()
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
        self.autosave()

    def apply_theme_qss(self):
        theme = get_theme(self.theme_combo.currentData() or "cnc")
        self.setStyleSheet(control_panel_qss(theme))

    def on_title_changed(self, text: str):
        self.scorebar.set_title(text)
        self.autosave()

    # ------------------------------------------------------------------
    def _build_config_dict(self) -> dict:
        return {
            "ffa": self.radio_ffa.isChecked(),
            "team_size": self.team_size_spin.value(),
            "ffa_count": self.ffa_count_spin.value(),
            "map_name": self.map_edit.text(),
            "theme": self.theme_combo.currentData(),
            "title": self.title_edit.text(),
            "players": [asdict(row.to_player()) for row in self.player_rows],
            "score_a": self.scorebar.state.score_a,
            "score_b": self.scorebar.state.score_b,
            "position": self.scorebar.position_key,
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

        self.title_edit.setText(data.get("title", "SCOREBAR"))

        self.scorebar.state.score_a = data.get("score_a", 0)
        self.scorebar.state.score_b = data.get("score_b", 0)

        position_key = data.get("position", "top_center")
        radio = self.position_radios.get(position_key)
        if radio:
            radio.setChecked(True)
        self.scorebar.set_position(position_key)

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
