import math
from dataclasses import dataclass


@dataclass(slots=True)
class Vec:
    x: float = 0.0
    y: float = 0.0

    def copy(self) -> "Vec":
        return Vec(self.x, self.y)

    def set(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def add(self, other: "Vec") -> None:
        self.x += other.x
        self.y += other.y

    def scale(self, k: float) -> None:
        self.x *= k
        self.y *= k

    def len(self) -> float:
        return math.hypot(self.x, self.y)

    def norm(self) -> None:
        d = self.len()
        if d > 0.0001:
            self.x /= d
            self.y /= d


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def dist_sq(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def clamp(v: float, lo: float, hi: float) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v
