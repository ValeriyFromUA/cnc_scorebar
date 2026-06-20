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
    # Форма/стиль панелі — щоб теми відрізнялись не лише кольором, а й
    # силуетом рамки та декоративними деталями (малюється в TacticalPanel):
    #   "notch"     — восьмикутник із зрізаними кутами (тактичний HUD)
    #   "brackets"  — прямокутник + кутові HUD-дужки (кіберпанк-приціл)
    #   "hexcut"    — "візор" зі скошеними верхніми кутами + лінія шва
    #   "carved"    — заокруглений прямокутник з різьбленою подвійною рамкою
    #   "brushed"   — заокруглений прямокутник з вертикальним металевим градієнтом
    #   "diamond"   — асиметрично зрізані протилежні кути + карбонове плетіння
    #   "glass"     — сильно заокруглений прямокутник зі скляним відблиском
    #   "scanline"  — прямокутник + HUD-дужки і горизонтальні скан-лінії
    #   "toxic"     — хвиляста "ослизла" рамка + токсичні бульбашки
    #   "concrete"  — прямокутник з кам'яно-сірою бетонною текстурою
    #   "hazard"    — прямокутник + чорно-жовті смуги техніки безпеки
    shape: str = "notch"


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
        shape="notch",
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
        shape="brackets",
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
        shape="hexcut",
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
        shape="carved",
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
        shape="brushed",
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
        shape="diamond",
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
        shape="glass",
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
        shape="scanline",
    ),
    "control": Theme(
        # Стиль гри Control (FBC): кам'яно-сіра бетонна архітектура Старого
        # дому — холодний бетон, лише тонкий темно-червоний натяк на Hiss.
        key="control",
        name="Control: Federal Bureau",
        bg="rgba(58, 58, 60, 235)",
        bg_alt="rgba(48, 48, 50, 245)",
        border="#8E8E93",
        accent="#C7C7CC",
        accent_secondary="#7A1F1F",
        text_primary="#EDEDED",
        text_secondary="#9A9A9E",
        team_a="#8E8E93",
        team_b="#7A1F1F",
        glow=False,
        font_family="Bank Gothic, Eurostile, Consolas, sans-serif",
        notch=4,
        shape="concrete",
    ),
    "toxic": Theme(
        # Токсична зона: ослизла зелена рамка з бульбашками отрути, як
        # радіоактивне болото.
        key="toxic",
        name="Токсична зона",
        bg="rgba(6, 18, 10, 225)",
        bg_alt="rgba(10, 26, 14, 235)",
        border="#7FFF3C",
        accent="#A8FF00",
        accent_secondary="#3E8914",
        text_primary="#E4FFD8",
        text_secondary="#8FCB6A",
        team_a="#A8FF00",
        team_b="#FF66C4",
        glow=True,
        font_family="Consolas, Eurostile, sans-serif",
        notch=8,
        shape="toxic",
    ),
    "black_cat": Theme(
        # Чорний кіт: глибокий чорний фон + золото (золотий — лише колір
        # акценту/рамки, без буквальних "очей" на панелі).
        key="black_cat",
        name="Чорний кіт",
        bg="rgba(4, 4, 4, 240)",
        bg_alt="rgba(10, 10, 10, 248)",
        border="#D4AF37",
        accent="#FFD700",
        accent_secondary="#8A6D1A",
        text_primary="#F1E6C8",
        text_secondary="#8A8262",
        team_a="#FFD700",
        team_b="#8A6D1A",
        glow=True,
        font_family="Cinzel, Georgia, Times New Roman, serif",
        notch=10,
        shape="carved",
    ),
    "half_life": Theme(
        # Half-Life: індустріальний HEV-стиль — холодний сталевий фон,
        # фірмовий HEV-оранжевий акцент і чорно-жовта смуга техніки безпеки.
        key="half_life",
        name="Half-Life: HEV",
        bg="rgba(16, 18, 16, 235)",
        bg_alt="rgba(22, 24, 22, 245)",
        border="#4A4A42",
        accent="#FF7A00",
        accent_secondary="#F2C200",
        text_primary="#E8E6DC",
        text_secondary="#9A9A8E",
        team_a="#FF7A00",
        team_b="#5A8C7A",
        glow=False,
        font_family="Eurostile, Arial Narrow, Segoe UI, sans-serif",
        notch=4,
        shape="hazard",
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
