import heapq
import math
from collections import deque
from typing import Iterable, Protocol

from .cfg import TILE


class GridLike(Protocol):
    w: int
    h: int

    def walk(self, c: int, r: int) -> bool: ...
    def is_wall(self, c: int, r: int) -> bool: ...


def aabb(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax <= bx + bw and ax + aw >= bx and ay <= by + bh and ay + ah >= by


def h(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neigh(grid: GridLike, cell: tuple[int, int]) -> Iterable[tuple[int, int]]:
    c, r = cell
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nc = c + dc
        nr = r + dr
        if 0 <= nc < grid.w and 0 <= nr < grid.h and grid.walk(nc, nr):
            yield nc, nr


def astar(grid: GridLike, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    if start == goal:
        return [start]
    if not grid.walk(*start) or not grid.walk(*goal):
        return []

    q: list[tuple[int, int, tuple[int, int]]] = []
    heapq.heappush(q, (0, 0, start))
    came: dict[tuple[int, int], tuple[int, int]] = {}
    cost: dict[tuple[int, int], int] = {start: 0}
    order = 0

    while q:
        _, _, cur = heapq.heappop(q)
        if cur == goal:
            break
        for nxt in neigh(grid, cur):
            ncost = cost[cur] + 1
            if nxt not in cost or ncost < cost[nxt]:
                cost[nxt] = ncost
                order += 1
                heapq.heappush(q, (ncost + h(nxt, goal), order, nxt))
                came[nxt] = cur

    if goal not in came:
        return []

    path = [goal]
    cur = goal
    while cur != start:
        cur = came[cur]
        path.append(cur)
    path.reverse()
    return path


def bfs(grid: GridLike, start: tuple[int, int]) -> set[tuple[int, int]]:
    if not grid.walk(*start):
        return set()
    seen = {start}
    q: deque[tuple[int, int]] = deque([start])
    while q:
        cur = q.popleft()
        for nxt in neigh(grid, cur):
            if nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return seen


def far_cell(grid: GridLike, start: tuple[int, int]) -> tuple[int, int]:
    seen = bfs(grid, start)
    if not seen:
        return start
    return max(seen, key=lambda p: h(p, start))


def los(grid: GridLike, ax: float, ay: float, bx: float, by: float) -> bool:
    dx = bx - ax
    dy = by - ay
    dist = math.hypot(dx, dy)
    if dist < 1:
        return True
    steps = max(1, int(dist / (TILE / 3)))
    for i in range(1, steps):
        t = i / steps
        x = ax + dx * t
        y = ay + dy * t
        c = int(x // TILE)
        r = int(y // TILE)
        if grid.is_wall(c, r):
            return False
    return True
