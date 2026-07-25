"""Статичні дані: фракції CnC Generals Zero Hour, країни/прапори, моделі гравця."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from resources import resource_path

FLAGS_DIR = resource_path("Icons", "Flags")
ARMIES_DIR = resource_path("Icons", "Armies")
GENERALS_DIR = resource_path("Icons", "Generals")


class FactionGroup(Enum):
    USA = "USA"
    CHINA = "China"
    GLA = "GLA"


# Лого армії (Icons/Armies) для базової фракції кожної групи — без
# кольорових варіантів, один файл на групу.
ARMY_LOGO_FILE: dict[FactionGroup, str] = {
    FactionGroup.USA: "SAFactionLogo144_US.png",
    FactionGroup.CHINA: "SNFactionLogo144_China.png",
    FactionGroup.GLA: "SUFactionLogo144_GLA.png",
}


@dataclass(frozen=True)
class Faction:
    key: str            # унікальний ідентифікатор, напр. "usa_lasr"
    name: str           # відображувана назва
    group: FactionGroup
    abbr: str           # коротка позначка для бейджа (3-5 символів)
    color: str          # основний колір фракції (HEX)
    color_dark: str      # темніший відтінок (для рамок/градієнтів)
    # Ім'я файлу генерала в Icons/Generals (без кольорового суфікса й
    # розширення), напр. "AirGeneral" -> "AirGeneral_blue.png". None для
    # базових фракцій (usa/china/gla) — для них береться лого армії.
    general_icon: str | None = None

    def icon_path(self, variant: str) -> Path:
        if self.general_icon:
            return GENERALS_DIR / f"{self.general_icon}_{variant}.png"
        return ARMIES_DIR / ARMY_LOGO_FILE[self.group]


# Базові фракції + генерали Zero Hour
FACTIONS: list[Faction] = [
    # --- USA ---
    Faction("usa", "USA", FactionGroup.USA, "USA", "#3D72B4", "#1F3A5F"),
    Faction("usa_super", "USA Superweapon", FactionGroup.USA, "SWG", "#6FA8DC", "#345A7A", "SuperWGeneral"),
    Faction("usa_laser", "USA Laser", FactionGroup.USA, "LSR", "#00C8FF", "#0A5C70", "LaserGeneral"),
    Faction("usa_air", "USA Air Force", FactionGroup.USA, "AF", "#4FA8E0", "#235077", "AirGeneral"),

    # --- China ---
    Faction("china", "China", FactionGroup.CHINA, "CHN", "#C0392B", "#6E1F16"),
    Faction("china_inf", "China Infantry", FactionGroup.CHINA, "INF", "#E05B3C", "#7A2D1C", "InfantryGeneral"),
    Faction("china_tank", "China Tank", FactionGroup.CHINA, "TNK", "#8B1A1A", "#4A0E0E", "TankGeneral"),
    Faction("china_nuke", "China Nuke", FactionGroup.CHINA, "NUK", "#A8C000", "#566200", "NukeGeneral"),

    # --- GLA ---
    Faction("gla", "GLA", FactionGroup.GLA, "GLA", "#9C7A3C", "#5A461F"),
    Faction("gla_toxin", "GLA Toxin", FactionGroup.GLA, "TOX", "#6B8E23", "#3A4D12", "ToxinGeneral"),
    Faction("gla_demo", "GLA Demolition", FactionGroup.GLA, "DEM", "#D2691E", "#7A3B10", "DemoGeneral"),
    Faction("gla_stealth", "GLA Stealth", FactionGroup.GLA, "STL", "#5B4B8A", "#2E264A", "StealthGeneral"),
]

FACTIONS_BY_KEY: dict[str, Faction] = {f.key: f for f in FACTIONS}


def get_faction(key: str) -> Faction:
    return FACTIONS_BY_KEY.get(key, FACTIONS[0])


# --------------------------------------------------------------------------
# Країни / прапори
# --------------------------------------------------------------------------
# Прапори — реальні PNG (Icons/Flags/<code>.png), а не юнікод-емодзі: Windows
# з 2021 навмисно показує замість емодзі-прапора лише дві літери коду
# країни, тож емодзі-варіант на Windows виглядав як "US"/"UA" замість іконки.

@dataclass(frozen=True)
class Country:
    code: str
    name: str

    @property
    def flag_path(self) -> Path:
        return FLAGS_DIR / f"{self.code.lower()}.png"


COUNTRIES: list[Country] = [
    Country("UA", "Ukraine"),
    Country("US", "United States"),
    Country("CA", "Canada"),
    Country("GB", "United Kingdom"),
    Country("DE", "Germany"),
    Country("FR", "France"),
    Country("PL", "Poland"),
    Country("NL", "Netherlands"),
    Country("BE", "Belgium"),
    Country("SE", "Sweden"),
    Country("FI", "Finland"),
    Country("NO", "Norway"),
    Country("DK", "Denmark"),
    Country("ES", "Spain"),
    Country("IT", "Italy"),
    Country("PT", "Portugal"),
    Country("AT", "Austria"),
    Country("CH", "Switzerland"),
    Country("CZ", "Czech Republic"),
    Country("SK", "Slovakia"),
    Country("HU", "Hungary"),
    Country("RO", "Romania"),
    Country("BG", "Bulgaria"),
    Country("GR", "Greece"),
    Country("TR", "Turkey"),
    Country("BY", "Belarus"),
    Country("LT", "Lithuania"),
    Country("LV", "Latvia"),
    Country("EE", "Estonia"),
    Country("KZ", "Kazakhstan"),
    Country("CN", "China"),
    Country("KR", "South Korea"),
    Country("JP", "Japan"),
    Country("AU", "Australia"),
    Country("NZ", "New Zealand"),
    Country("BR", "Brazil"),
    Country("AR", "Argentina"),
    Country("MX", "Mexico"),
    Country("IN", "India"),
    Country("IL", "Israel"),
    Country("SA", "Saudi Arabia"),
    Country("AE", "United Arab Emirates"),
    Country("EG", "Egypt"),
    Country("ZA", "South Africa"),
    Country("RS", "Serbia"),
    Country("HR", "Croatia"),
    Country("SI", "Slovenia"),
    Country("IE", "Ireland"),
    Country("IS", "Iceland"),
    Country("MD", "Moldova"),
    Country("GE", "Georgia"),
    Country("AM", "Armenia"),
    Country("AZ", "Azerbaijan"),
]

COUNTRIES_BY_CODE: dict[str, Country] = {c.code: c for c in COUNTRIES}


def get_country(code: str) -> Country:
    if code in COUNTRIES_BY_CODE:
        return COUNTRIES_BY_CODE[code]
    return Country(code.upper() if code else "??", code or "Unknown")


# --------------------------------------------------------------------------
# Кольори гравців (кольоровий трикутник-маркер на скорбарі)
# --------------------------------------------------------------------------

PLAYER_COLORS: list[tuple[str, str, str]] = [
    # (key, назва українською, HEX)
    ("red", "Червоний", "#E74C3C"),
    ("blue", "Синій", "#3498DB"),
    ("green", "Зелений", "#2ECC71"),
    ("yellow", "Жовтий", "#F1C40F"),
    ("orange", "Помаранчевий", "#E67E22"),
    ("purple", "Фіолетовий", "#9B59B6"),
    ("cyan", "Блакитний", "#7FE3EC"),
    ("pink", "Рожевий", "#FF6FB0"),
]

PLAYER_COLORS_BY_KEY: dict[str, tuple[str, str]] = {key: (label, hex_) for key, label, hex_ in PLAYER_COLORS}


def get_player_color_hex(key: str | None) -> str | None:
    if not key:
        return None
    entry = PLAYER_COLORS_BY_KEY.get(key)
    return entry[1] if entry else None


# --------------------------------------------------------------------------
# Модель гравця / матчу
# --------------------------------------------------------------------------

@dataclass
class Player:
    name: str = "Player"
    country_code: str = "UA"
    faction_key: str = "usa"
    team: int = 0       # 0 = ліва/команда A, 1 = права/команда B (FFA: ігнорується)
    score: int = 0
    division: str | None = None  # дивізіон з cnc-general-ukraine.org, якщо гравця обрано зі списку
    elo: int | None = None       # ELO з cnc-general-ukraine.org, якщо гравця обрано зі списку
    color_key: str | None = None  # ключ кольору гравця (див. PLAYER_COLORS), None = без маркера

    @property
    def faction(self) -> Faction:
        return get_faction(self.faction_key)

    @property
    def country(self) -> Country:
        return get_country(self.country_code)


@dataclass
class MatchState:
    """Повний стан матчу, який рендерить scorebar."""
    ffa: bool = False
    team_size: int = 1          # 1..4 для командних режимів
    players: list[Player] = field(default_factory=list)
    score_a: int = 0            # рахунок команди A (для командних режимів)
    score_b: int = 0            # рахунок команди B
    map_name: str = ""

    @property
    def mode_label(self) -> str:
        if self.ffa:
            return f"FFA {len(self.players)}P"
        return f"{self.team_size}v{self.team_size}"
