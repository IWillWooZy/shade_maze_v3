SCREEN_W = 960
SCREEN_H = 640
TILE = 32
MAP_W = 64
MAP_H = 48
FIXED_DT = 1.0 / 60.0
MAX_FRAME = 0.25

PLAYER_W = 22
PLAYER_H = 22
PLAYER_SPEED = 165.0
PLAYER_ACCEL = 15.0
PLAYER_DECEL = 20.0
PLAYER_STOP = PLAYER_DECEL
VIEW_LERP = 24.0
PLAYER_HP = 100
ARMOR_MAX = 50
HEAL_AMOUNT = 35
ARMOR_ADD = 25
DASH_SPEED = 430.0
DASH_TIME = 0.17
DASH_CD = 2.4
RAGE_TIME = 8.0
RAGE_CD = 18.0
RAGE_SPEED_MUL = 1.28
RAGE_DMG_MUL = 1.45

ENEMY_W = 22
ENEMY_H = 22
MAX_LEVEL = 10
ENEMY_SPEED_L1 = 70.0
ENEMY_SPEED_L10 = 150.0
ENEMY_DMG_L1 = 5
ENEMY_DMG_L10 = 24
ENEMY_SEE = 235.0
ENEMY_LOSE = 330.0
ENEMY_ATTACK = 34.0
ENEMY_COOLDOWN = 0.75
CHASE_MUL = 1.12
PATH_DELAY = 0.22
SHOT_RANGE = 260.0
SHOT_MIN = 120.0
SHOT_CD = 1.35
BOLT_SPEED = 245.0
BOLT_SIZE = 8
TANK_HP_MUL = 2.8
ALERT_LIGHT_R = 175.0
ALERT_ADD = 3


def level_t(level_no: int) -> float:
    n = max(1, min(MAX_LEVEL, int(level_no)))
    return (n - 1) / max(1, MAX_LEVEL - 1)


def enemy_speed(level_no: int) -> float:
    t = level_t(level_no)
    return ENEMY_SPEED_L1 + (ENEMY_SPEED_L10 - ENEMY_SPEED_L1) * t


def enemy_dmg(level_no: int) -> int:
    t = level_t(level_no)
    return int(round(ENEMY_DMG_L1 + (ENEMY_DMG_L10 - ENEMY_DMG_L1) * t))


ENEMY_SPEED = enemy_speed(1)
ENEMY_DMG = enemy_dmg(1)
BLADE_SIZE = 22
BLADE_RANGE = 82.0
BLADE_RESPAWN = 9.5
BLADE_COOLDOWN = 0.28

WEAPON_SIZE = 22
WEAPON_MAX = 3
WEAPON_KINDS = ("blade", "shuriken", "gun")
WEAPON_NAMES = {
    "blade": "клинок",
    "shuriken": "сюрикен",
    "gun": "искромёт",
}
WEAPON_RANGE = {
    "blade": 84.0,
    "shuriken": 178.0,
    "gun": 255.0,
}
WEAPON_DMG = {
    "blade": 22,
    "shuriken": 18,
    "gun": 30,
}
GUN_MAX = 3
GUN_COST = 1
WEAPON_AMMO = {
    "blade": 1,
    "shuriken": 1,
    "gun": GUN_MAX,
}
WEAPON_RESPAWN = {
    "blade": 9.5,
    "shuriken": 10.5,
    "gun": 13.0,
}

SPARKS_NEEDED = 5
SPARKS_EXTRA = 6
SPARKS_ON_MAP = SPARKS_NEEDED + SPARKS_EXTRA
KEY_KINDS = ("red", "blue", "green")
KEY_NAMES = {
    "red": "красный",
    "blue": "синий",
    "green": "зелёный",
}

SKILL_KINDS = ("spd", "pow", "vit", "dash", "rage", "mag")
SKILL_NAMES = {
    "spd": "скорость",
    "pow": "сила",
    "vit": "живучесть",
    "dash": "рывок",
    "rage": "ярость",
    "mag": "магнит искр",
}
SKILL_MAX = {
    "spd": 3,
    "pow": 3,
    "vit": 3,
    "dash": 1,
    "rage": 1,
    "mag": 2,
}
SKILL_COST = {
    "spd": 2,
    "pow": 2,
    "vit": 2,
    "dash": 3,
    "rage": 4,
    "mag": 2,
}
SKILL_DESC = {
    "spd": "+8% скорости за уровень",
    "pow": "+20% урона за уровень",
    "vit": "+15 max HP за уровень",
    "dash": "Shift: короткий рывок",
    "rage": "F: 8 сек. скорость и урон",
    "mag": "искры и опыт тянутся ближе",
}
XP_PICKUP_RANGE = 44.0
MAGNET_RANGE = 88.0

PARTICLE_LIMIT = 360
LIGHT_R = 285.0
LIGHT_MIN = 0.08
FLOOR_LIGHT_MIN = 0.17
WALL_LIGHT_MIN = 0.045
SPRITE_MIN = 0.26

MAZE_STEP = 7
ROAD_W = 3
DIR_BIAS = 0.72
LOOP_RATE = 0.14

FLOOR = 0
WALL = 1

COL = {
    "bg": "#0a0d14",
    "panel": "#111827",
    "panel2": "#172033",
    "floor": "#46515f",
    "floor2": "#505d6d",
    "floor_grid": "#303946",
    "wall": "#0e131c",
    "wall2": "#182131",
    "wall_edge": "#35445b",
    "wall_hi": "#52647c",
    "player": "#77d5ff",
    "player_hurt": "#ff8888",
    "player_hood": "#4fbfff",
    "player_coat": "#244d73",
    "player_coat2": "#2f6695",
    "player_body": "#4fbfff",
    "player_body2": "#244d73",
    "player_boot": "#16243a",
    "player_face": "#ffe4bd",
    "player_eye": "#f7ffff",
    "player_scarf": "#ffd166",
    "player_trim": "#e8fbff",
    "spark": "#ffd866",
    "spark2": "#fff071",
    "spark_core": "#fffaf0",
    "spark_glow": "#ffb84d",
    "key": "#ff9f43",
    "key_red": "#ff5d73",
    "key_blue": "#63b3ff",
    "key_green": "#7cff91",
    "xp": "#c77dff",
    "xp_core": "#fff0ff",
    "blade": "#b8f5ff",
    "blade_core": "#ffffff",
    "blade_edge": "#5bd8ff",
    "shuriken": "#d9e2ff",
    "shuriken_edge": "#91a7ff",
    "gun": "#ffdd8a",
    "gun_edge": "#ff9f43",
    "slash": "#f6ffff",
    "exit": "#7cff91",
    "exit_lock": "#9da5b4",
    "alert": "#ff5d73",
    "heal": "#6dff9c",
    "heal_core": "#effff3",
    "armor": "#9fb8ff",
    "armor_core": "#eaf0ff",
    "enemy_patrol": "#8ce6c4",
    "enemy_chase": "#ffd166",
    "enemy_attack": "#ff5d73",
    "enemy_body": "#2c3444",
    "enemy_body2": "#3b465c",
    "enemy_eye": "#f7fff9",
    "enemy_shooter": "#c77dff",
    "enemy_shooter2": "#51406f",
    "enemy_tank": "#ff8a5b",
    "enemy_tank2": "#5a3130",
    "bolt": "#ff97f3",
    "ui": "#e8edf2",
    "muted": "#9da5b4",
    "dark": "#030407",
    "hp": "#ff5d73",
    "hp_bg": "#3a1d27",
    "armor_bar": "#9fb8ff",
    "armor_bg": "#20283d",
    "debug": "#a7ffef",
    "path": "#ffeaa7",
    "hit": "#ff97c8",
}
