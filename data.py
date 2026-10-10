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

# Сентинел для "без генерала" — окремий від "" (яке combo_get_data
# повертає при відсутності вибору в комбобоксі), щоб не сплутати навмисну
# відсутність генерала з помилкою читання комбобокса.
NO_FACTION_KEY = "none"


def get_faction(key: str) -> Faction | None:
    if key == NO_FACTION_KEY:
        return None
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


# Всі країни, крім України (вона окремо, перша) і росії (окремо, остання,
# з гівняшкою замість прапора — Icons/Flags/ru.png) — порядок тут
# неважливий, підсумковий список нижче сортується за назвою.
_OTHER_COUNTRIES: list[Country] = [
    Country("AL", "Albania"),
    Country("AD", "Andorra"),
    Country("AT", "Austria"),
    Country("BY", "Belarus"),
    Country("BE", "Belgium"),
    Country("BA", "Bosnia and Herzegovina"),
    Country("BG", "Bulgaria"),
    Country("HR", "Croatia"),
    Country("CZ", "Czech Republic"),
    Country("DK", "Denmark"),
    Country("EE", "Estonia"),
    Country("FI", "Finland"),
    Country("FR", "France"),
    Country("DE", "Germany"),
    Country("GR", "Greece"),
    Country("HU", "Hungary"),
    Country("IS", "Iceland"),
    Country("IE", "Ireland"),
    Country("IT", "Italy"),
    Country("XK", "Kosovo"),
    Country("LV", "Latvia"),
    Country("LI", "Liechtenstein"),
    Country("LT", "Lithuania"),
    Country("LU", "Luxembourg"),
    Country("MT", "Malta"),
    Country("MD", "Moldova"),
    Country("MC", "Monaco"),
    Country("ME", "Montenegro"),
    Country("NL", "Netherlands"),
    Country("MK", "North Macedonia"),
    Country("NO", "Norway"),
    Country("PL", "Poland"),
    Country("PT", "Portugal"),
    Country("RO", "Romania"),
    Country("SM", "San Marino"),
    Country("RS", "Serbia"),
    Country("SK", "Slovakia"),
    Country("SI", "Slovenia"),
    Country("ES", "Spain"),
    Country("SE", "Sweden"),
    Country("CH", "Switzerland"),
    Country("GB", "United Kingdom"),
    Country("VA", "Vatican City"),
    Country("AF", "Afghanistan"),
    Country("AM", "Armenia"),
    Country("AZ", "Azerbaijan"),
    Country("BH", "Bahrain"),
    Country("BD", "Bangladesh"),
    Country("BT", "Bhutan"),
    Country("BN", "Brunei"),
    Country("KH", "Cambodia"),
    Country("CN", "China"),
    Country("CY", "Cyprus"),
    Country("GE", "Georgia"),
    Country("IN", "India"),
    Country("ID", "Indonesia"),
    Country("IR", "Iran"),
    Country("IQ", "Iraq"),
    Country("IL", "Israel"),
    Country("JP", "Japan"),
    Country("JO", "Jordan"),
    Country("KZ", "Kazakhstan"),
    Country("KW", "Kuwait"),
    Country("KG", "Kyrgyzstan"),
    Country("LA", "Laos"),
    Country("LB", "Lebanon"),
    Country("MY", "Malaysia"),
    Country("MV", "Maldives"),
    Country("MN", "Mongolia"),
    Country("MM", "Myanmar"),
    Country("NP", "Nepal"),
    Country("KP", "North Korea"),
    Country("OM", "Oman"),
    Country("PK", "Pakistan"),
    Country("PS", "Palestine"),
    Country("PH", "Philippines"),
    Country("QA", "Qatar"),
    Country("SA", "Saudi Arabia"),
    Country("SG", "Singapore"),
    Country("KR", "South Korea"),
    Country("LK", "Sri Lanka"),
    Country("SY", "Syria"),
    Country("TW", "Taiwan"),
    Country("TJ", "Tajikistan"),
    Country("TH", "Thailand"),
    Country("TL", "Timor-Leste"),
    Country("TR", "Turkey"),
    Country("TM", "Turkmenistan"),
    Country("AE", "United Arab Emirates"),
    Country("UZ", "Uzbekistan"),
    Country("VN", "Vietnam"),
    Country("YE", "Yemen"),
    Country("DZ", "Algeria"),
    Country("AO", "Angola"),
    Country("BJ", "Benin"),
    Country("BW", "Botswana"),
    Country("BF", "Burkina Faso"),
    Country("BI", "Burundi"),
    Country("CV", "Cape Verde"),
    Country("CM", "Cameroon"),
    Country("CF", "Central African Republic"),
    Country("TD", "Chad"),
    Country("KM", "Comoros"),
    Country("CG", "Congo"),
    Country("CD", "DR Congo"),
    Country("CI", "Côte d'Ivoire"),
    Country("DJ", "Djibouti"),
    Country("EG", "Egypt"),
    Country("GQ", "Equatorial Guinea"),
    Country("ER", "Eritrea"),
    Country("SZ", "Eswatini"),
    Country("ET", "Ethiopia"),
    Country("GA", "Gabon"),
    Country("GM", "Gambia"),
    Country("GH", "Ghana"),
    Country("GN", "Guinea"),
    Country("GW", "Guinea-Bissau"),
    Country("KE", "Kenya"),
    Country("LS", "Lesotho"),
    Country("LR", "Liberia"),
    Country("LY", "Libya"),
    Country("MG", "Madagascar"),
    Country("MW", "Malawi"),
    Country("ML", "Mali"),
    Country("MR", "Mauritania"),
    Country("MU", "Mauritius"),
    Country("MA", "Morocco"),
    Country("MZ", "Mozambique"),
    Country("NA", "Namibia"),
    Country("NE", "Niger"),
    Country("NG", "Nigeria"),
    Country("RW", "Rwanda"),
    Country("ST", "São Tomé and Príncipe"),
    Country("SN", "Senegal"),
    Country("SC", "Seychelles"),
    Country("SL", "Sierra Leone"),
    Country("SO", "Somalia"),
    Country("ZA", "South Africa"),
    Country("SS", "South Sudan"),
    Country("SD", "Sudan"),
    Country("TZ", "Tanzania"),
    Country("TG", "Togo"),
    Country("TN", "Tunisia"),
    Country("UG", "Uganda"),
    Country("ZM", "Zambia"),
    Country("ZW", "Zimbabwe"),
    Country("AG", "Antigua and Barbuda"),
    Country("BS", "Bahamas"),
    Country("BB", "Barbados"),
    Country("BZ", "Belize"),
    Country("CA", "Canada"),
    Country("CR", "Costa Rica"),
    Country("CU", "Cuba"),
    Country("DM", "Dominica"),
    Country("DO", "Dominican Republic"),
    Country("SV", "El Salvador"),
    Country("GD", "Grenada"),
    Country("GT", "Guatemala"),
    Country("HT", "Haiti"),
    Country("HN", "Honduras"),
    Country("JM", "Jamaica"),
    Country("MX", "Mexico"),
    Country("NI", "Nicaragua"),
    Country("PA", "Panama"),
    Country("KN", "Saint Kitts and Nevis"),
    Country("LC", "Saint Lucia"),
    Country("VC", "Saint Vincent and the Grenadines"),
    Country("TT", "Trinidad and Tobago"),
    Country("US", "United States"),
    Country("AR", "Argentina"),
    Country("BO", "Bolivia"),
    Country("BR", "Brazil"),
    Country("CL", "Chile"),
    Country("CO", "Colombia"),
    Country("EC", "Ecuador"),
    Country("GY", "Guyana"),
    Country("PY", "Paraguay"),
    Country("PE", "Peru"),
    Country("SR", "Suriname"),
    Country("UY", "Uruguay"),
    Country("VE", "Venezuela"),
    Country("AU", "Australia"),
    Country("FJ", "Fiji"),
    Country("KI", "Kiribati"),
    Country("MH", "Marshall Islands"),
    Country("FM", "Micronesia"),
    Country("NR", "Nauru"),
    Country("NZ", "New Zealand"),
    Country("PW", "Palau"),
    Country("PG", "Papua New Guinea"),
    Country("WS", "Samoa"),
    Country("SB", "Solomon Islands"),
    Country("TO", "Tonga"),
    Country("TV", "Tuvalu"),
    Country("VU", "Vanuatu"),
]

# Сентинел "без прапора": файлу Icons/Flags/none.png немає, тож скорбар
# просто не малює прапор (як і для невідомих кодів у get_country).
NO_FLAG_CODE = "NONE"

# Порядок у комбобоксі: "без прапора" зверху (як "Без генерала" у
# фракціях), далі Україна, піратський прапор (це не країна, тому за
# алфавітом його шукати незручно), решта — за алфавітом, russia — в кінці
# і навмисно з малої літери.
COUNTRIES: list[Country] = [
    Country(NO_FLAG_CODE, "— Без прапора —"),
    Country("UA", "Ukraine"),
    Country("PIRATE", "Pirate"),
    *sorted(_OTHER_COUNTRIES, key=lambda c: c.name),
    Country("RU", "russia"),
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
    def faction(self) -> Faction | None:
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
