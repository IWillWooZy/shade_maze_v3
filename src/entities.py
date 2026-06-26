from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterable

from .cfg import ENEMY_DMG, ENEMY_H, ENEMY_W, PLAYER_H, PLAYER_HP, PLAYER_W, SKILL_KINDS


class GameState(Enum):
    MENU = auto()
    PLAY = auto()
    INV = auto()
    PAUSE = auto()
    WIN = auto()
    LOSE = auto()


class EnemyState(Enum):
    PATROL = auto()
    CHASE = auto()
    ATTACK = auto()


@dataclass(slots=True)
class Actor:
    x: float
    y: float
    w: int
    h: int
    speed: float
    hp: int = 1
    vx: float = 0.0
    vy: float = 0.0
    alive: bool = True
    view_x: float = 0.0
    view_y: float = 0.0
    anim_t: float = 0.0
    anim_i: int = 0

    def __post_init__(self) -> None:
        self.view_x = self.x
        self.view_y = self.y

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def rect(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h

    def stop(self) -> None:
        self.vx = 0.0
        self.vy = 0.0


@dataclass(slots=True)
class Player(Actor):
    gems: int = 0
    has_key: bool = False
    keys: set[str] = field(default_factory=set)
    wp: str = ""
    inv: dict[str, int] = field(default_factory=dict)
    armor: int = 0
    max_hp: int = PLAYER_HP
    xp: int = 0
    skills: dict[str, int] = field(default_factory=lambda: {k: 0 for k in SKILL_KINDS})
    face_x: float = 1.0
    face_y: float = 0.0
    hurt_t: float = 0.0
    atk_t: float = 0.0
    atk_wp: str = ""
    atk_x: float = 0.0
    atk_y: float = 0.0
    dash_t: float = 0.0
    dash_cd: float = 0.0
    dash_x: float = 1.0
    dash_y: float = 0.0
    rage_t: float = 0.0
    rage_cd: float = 0.0

    @classmethod
    def make(cls, x: float, y: float, speed: float) -> "Player":
        return cls(x, y, PLAYER_W, PLAYER_H, speed, hp=PLAYER_HP)

    def weapon_name(self) -> str:
        names = {"blade": "клинок", "shuriken": "сюрикен", "gun": "искромёт"}
        return names.get(self.wp, "нет")


@dataclass(slots=True)
class Enemy(Actor):
    dmg: int = ENEMY_DMG
    max_hp: int = 20
    kind: str = "guard"
    xp: int = 1
    state: EnemyState = EnemyState.PATROL
    path: list[tuple[int, int]] = field(default_factory=list)
    patrol: list[tuple[int, int]] = field(default_factory=list)
    wp: int = 0
    path_t: float = 0.0
    atk_t: float = 0.0
    lost_t: float = 0.0
    last_cell: tuple[int, int] | None = None

    @classmethod
    def make(
        cls,
        x: float,
        y: float,
        speed: float,
        patrol: Iterable[tuple[int, int]],
        dmg: int = ENEMY_DMG,
        kind: str = "guard",
        hp: int = 20,
        xp: int = 1,
        size: int = ENEMY_W,
    ) -> "Enemy":
        return cls(x, y, size, size, speed, hp=hp, dmg=dmg, max_hp=hp, kind=kind, xp=xp, patrol=list(patrol))


@dataclass(slots=True)
class Item:
    kind: str
    x: float
    y: float
    w: int = 18
    h: int = 18
    alive: bool = True
    view_x: float = 0.0
    view_y: float = 0.0
    anim_t: float = 0.0
    anim_i: int = 0
    val: int = 0

    def __post_init__(self) -> None:
        self.view_x = self.x
        self.view_y = self.y

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def rect(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h


@dataclass(slots=True)
class Shot:
    x: float
    y: float
    vx: float
    vy: float
    dmg: int
    kind: str = "bolt"
    w: int = 8
    h: int = 8
    alive: bool = True
    life: float = 3.0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def rect(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h


@dataclass(slots=True)
class Particle:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    life: float = 0.0
    age: float = 0.0
    size: float = 3.0
    kind: str = "spark"
    alive: bool = False

    def reset(self, x: float, y: float, vx: float, vy: float, life: float, size: float, kind: str) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.age = 0.0
        self.size = size
        self.kind = kind
        self.alive = True

    def update(self, dt: float, grav: float = 0.0, drag: float = 0.96) -> None:
        self.vy += grav * dt
        d = drag ** (dt * 60.0)
        self.vx *= d
        self.vy *= d
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt
        if self.age >= self.life:
            self.alive = False

    def left(self) -> float:
        if self.life <= 0:
            return 0.0
        return max(0.0, 1.0 - self.age / self.life)
