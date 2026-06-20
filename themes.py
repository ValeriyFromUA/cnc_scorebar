"""Теми оформлення: CnC Generals (тактичний HUD), Neon/Cyberpunk, Crysis 3 і Відьмак 3.

Теми описують палітру + параметри кутових засічок панелей. QSS використовується
для звичайних віджетів control_panel, а кутові "tactical" панелі в scorebar
малюються вручну (QPainterPath) у paintEvent, бо CSS не вміє косих кутів.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    name: str

    bg: str              # фон панелі (з альфою, формат rgba(...))
    bg_alt: str          # фон альтернативної панелі (центральний рахунок)
    border: str          # колір рамки/контуру
    accent: str          # головний акцент (золото / неон-циан)
    accent_secondary: str
    text_primary: str
    text_secondary: str
    team_a: str          # підсвітка команди A
    team_b: str          # підсвітка команди B
    glow: bool           # чи додавати неоновий drop-shadow
    font_family: str
    notch: int           # розмір кутової засічки (px)
    corner_cut: int = 0  # додатковий зріз для "tactical" рамки


THEMES: dict[str, Theme] = {
    "cnc": Theme(
        key="cnc",
        name="CnC Generals: Zero Hour",
        bg="rgba(12, 14, 10, 230)",
        bg_alt="rgba(20, 18, 8, 240)",
        border="#C9A227",
        accent="#D4AF37",
        accent_secondary="#8A6D1A",
        text_primary="#F1E6C8",
        text_secondary="#A89B6C",
        team_a="#3D72B4",
        team_b="#C0392B",
        glow=False,
        font_family="Eurostile, Arial Narrow, Segoe UI, sans-serif",
        notch=14,
    ),
    "neon": Theme(
        key="neon",
        name="Neon / Cyberpunk",
        bg="rgba(8, 6, 20, 220)",
        bg_alt="rgba(14, 8, 28, 235)",
        border="#00E5FF",
        accent="#FF2A6D",
        accent_secondary="#00E5FF",
        text_primary="#E8F9FF",
        text_secondary="#7FB8C9",
        team_a="#00E5FF",
        team_b="#FF2A6D",
        glow=True,
        font_family="Consolas, Orbitron, Segoe UI, sans-serif",
        notch=10,
    ),
    "crysis3": Theme(
        # Палітра відтворює нанокостюм-візор з Crysis (1/2/3 та Remastered
        # Trilogy): напівпрозоре скло шолома, тонкі ціанові HUD-лінії,
        # помаранчевий — колір тривоги/енергії та режиму "Армор".
        key="crysis3",
        name="Crysis 3: Nanosuit Visor",
        bg="rgba(4, 14, 22, 150)",
        bg_alt="rgba(2, 20, 32, 170)",
        border="#1ED8FF",
        accent="#3DE8FF",
        accent_secondary="#FF7A1A",
        text_primary="#E8FBFF",
        text_secondary="#6FA8C0",
        team_a="#1ED8FF",
        team_b="#FF7A1A",
        glow=True,
        font_family="Eurostile, Bank Gothic, Consolas, sans-serif",
        notch=10,
    ),
    "witcher3": Theme(
        key="witcher3",
        name="The Witcher 3: School of the Wolf",
        bg="rgba(18, 14, 10, 235)",
        bg_alt="rgba(26, 18, 10, 245)",
        border="#B08D57",
        accent="#C9952C",
        accent_secondary="#7A1F1F",
        text_primary="#EDE0C8",
        text_secondary="#A89472",
        team_a="#8C2F2F",
        team_b="#2F4F3A",
        glow=False,
        font_family="Cinzel, Georgia, Times New Roman, serif",
        notch=8,
    ),
    "metal": Theme(
        # Шліфована сталь: холодні сріблясто-сірі тони, без неонового сяйва —
        # суворий індустріальний HUD.
        key="metal",
        name="Метал: Brushed Steel",
        bg="rgba(28, 30, 32, 235)",
        bg_alt="rgba(38, 40, 42, 245)",
        border="#9FA6AD",
        accent="#C7CDD3",
        accent_secondary="#5A6268",
        text_primary="#EDEFF1",
        text_secondary="#9AA1A8",
        team_a="#4A90D9",
        team_b="#B0352B",
        glow=False,
        font_family="Segoe UI, Arial, sans-serif",
        notch=6,
    ),
    "carbon": Theme(
        # Карбонове волокно: глибокий матовий чорний + гоночний червоний
        # акцент, як на спортивних авто/мотошоломах.
        key="carbon",
        name="Карбон: Carbon Fiber",
        bg="rgba(8, 8, 10, 235)",
        bg_alt="rgba(14, 14, 16, 245)",
        border="#3A3A3E",
        accent="#E10600",
        accent_secondary="#8A8A8E",
        text_primary="#F0F0F0",
        text_secondary="#8A8A8E",
        team_a="#E10600",
        team_b="#3A8FD9",
        glow=False,
        font_family="Eurostile, Bank Gothic, Consolas, sans-serif",
        notch=8,
    ),
    "glass": Theme(
        # Скло / "frosted glass": світла напівпрозора панель у стилі
        # сучасного UI (Fluent/Aero) — м'яке сяйво, блакитний акцент.
        key="glass",
        name="Скло: Frosted Glass",
        bg="rgba(230, 240, 250, 130)",
        bg_alt="rgba(255, 255, 255, 150)",
        border="#FFFFFF",
        accent="#5AC8FA",
        accent_secondary="#0A84FF",
        text_primary="#1C1C1E",
        text_secondary="#5B5B5E",
        team_a="#5AC8FA",
        team_b="#FF9F0A",
        glow=True,
        font_family="Segoe UI, San Francisco, Helvetica Neue, sans-serif",
        notch=12,
    ),
    "terminator": Theme(
        # Зір T-800: чорно-червоний бойовий HUD кіборга, моноширинний
        # "сканерний" текст.
        key="terminator",
        name="Терминатор: T-800 HUD",
        bg="rgba(8, 0, 0, 210)",
        bg_alt="rgba(16, 0, 0, 225)",
        border="#FF1A1A",
        accent="#FF0000",
        accent_secondary="#8A0000",
        text_primary="#FFD0D0",
        text_secondary="#B33333",
        team_a="#FF0000",
        team_b="#CCCCCC",
        glow=True,
        font_family="Consolas, Courier New, monospace",
        notch=6,
    ),
}

DEFAULT_THEME_KEY = "cnc"


def get_theme(key: str) -> Theme:
    return THEMES.get(key, THEMES[DEFAULT_THEME_KEY])


def control_panel_qss(theme: Theme) -> str:
    """QSS для звичайного (не-overlay) вікна панелі керування.

    Фон панелі керування завжди темний (фіксовані hex-кольори нижче), на
    відміну від theme.bg, який розрахований на власний фон оверлею (напр.
    у темі "glass" theme.text_primary темний — годиться для світлого
    скляного оверлею, але був би невидимий на темному тлі панелі). Тому тут
    текст використовує власні, завжди світлі кольори, а не theme.text_*.
    """
    text_color = "#EDE7D6"
    text_secondary = "#A89B6C"
    return f"""
    QWidget {{
        background-color: #14130f;
        color: {text_color};
        font-family: {theme.font_family};
        font-size: 12px;
    }}
    QGroupBox {{
        border: 1px solid {theme.border};
        border-radius: 4px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
        color: {theme.accent};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    QPushButton {{
        background-color: #232017;
        border: 1px solid {theme.border};
        border-radius: 3px;
        padding: 5px 10px;
        color: {text_color};
    }}
    QPushButton:hover {{
        background-color: {theme.accent};
        color: #14130f;
    }}
    QPushButton:pressed {{
        background-color: {theme.accent_secondary};
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background-color: #1c1a13;
        border: 1px solid #4a4530;
        border-radius: 3px;
        padding: 3px 6px;
        color: {text_color};
        selection-background-color: {theme.accent};
    }}
    QComboBox QAbstractItemView {{
        background-color: #1c1a13;
        color: {text_color};
        selection-background-color: {theme.accent};
        selection-color: #14130f;
    }}
    QTabWidget::pane {{
        border: 1px solid {theme.border};
    }}
    QTabBar::tab {{
        background: #1c1a13;
        color: {text_secondary};
        padding: 6px 14px;
        border: 1px solid #4a4530;
    }}
    QTabBar::tab:selected {{
        background: {theme.accent};
        color: #14130f;
    }}
    QLabel#sectionTitle {{
        color: {theme.accent};
        font-weight: bold;
        font-size: 13px;
    }}
    QLabel#footerLabel {{
        color: {text_secondary};
        font-size: 9px;
    }}
    QScrollArea {{
        border: none;
    }}
    """
