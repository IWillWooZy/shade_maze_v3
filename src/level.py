import random
from collections import deque
from dataclasses import dataclass

from .alg import bfs
from .cfg import FLOOR, LOOP_RATE, MAP_H, MAP_W, MAZE_STEP, ROAD_W, DIR_BIAS, TILE, WALL


@dataclass(slots=True)
class Level:
    grid: list[list[int]]
    seed: int
    start: tuple[int, int]
    exit: tuple[int, int]

    @property
    def w(self) -> int:
        return len(self.grid[0])

    @property
    def h(self) -> int:
        return len(self.grid)

    @property
    def px_w(self) -> int:
        return self.w * TILE

    @property
    def px_h(self) -> int:
        return self.h * TILE

    def in_map(self, c: int, r: int) -> bool:
        return 0 <= c < self.w and 0 <= r < self.h

    def is_wall(self, c: int, r: int) -> bool:
        if not self.in_map(c, r):
            return True
        return self.grid[r][c] == WALL

    def walk(self, c: int, r: int) -> bool:
        return self.in_map(c, r) and self.grid[r][c] == FLOOR

    def to_cell(self, x: float, y: float) -> tuple[int, int]:
        return int(x // TILE), int(y // TILE)

    def cell_pos(self, cell: tuple[int, int]) -> tuple[float, float]:
        c, r = cell
        return c * TILE + TILE / 2, r * TILE + TILE / 2

    def rect_pos(self, cell: tuple[int, int], w: int, h: int) -> tuple[float, float]:
        x, y = self.cell_pos(cell)
        return x - w / 2, y - h / 2

    def floor_cells(self) -> list[tuple[int, int]]:
        res = []
        for r, row in enumerate(self.grid):
            for c, v in enumerate(row):
                if v == FLOOR:
                    res.append((c, r))
        return res


@dataclass(slots=True)
class _Meta:
    xs: list[int]
    ys: list[int]
    edges: set[tuple[tuple[int, int], tuple[int, int]]]


def make_level(seed: int | None = None, w: int = MAP_W, h: int = MAP_H) -> Level:
    if seed is None:
        seed = random.randint(100000, 999999)
    rng = random.Random(seed)
    grid = [[WALL for _ in range(w)] for _ in range(h)]

    xs, ys = _axes(w, h)
    start = _center_node(xs, ys, w, h)
    meta = _dig_maze(grid, xs, ys, start, rng)
    _open_loops(grid, meta, rng)
    _clear_start(grid, start)

    reached = bfs(_Grid(grid), start)
    min_floor = max(12, (w * h) // 4)
    if len(reached) < min_floor:
        meta = _dig_maze(grid, xs, ys, start, rng)
        _open_loops(grid, meta, rng)
        _clear_start(grid, start)
        reached = bfs(_Grid(grid), start)

    out = _far_path_cell(grid, start, rng)
    return Level(grid, seed, start, out)


def _axes(w: int, h: int) -> tuple[list[int], list[int]]:
    pad = max(ROAD_W, 3)
    step = min(MAZE_STEP, max(4, min(w, h) // 4))
    xs = list(range(pad, max(pad + 1, w - pad), step))
    ys = list(range(pad, max(pad + 1, h - pad), step))

    if len(xs) < 2:
        xs = [max(1, w // 3), min(w - 2, max(1, w * 2 // 3))]
    if len(ys) < 2:
        ys = [max(1, h // 3), min(h - 2, max(1, h * 2 // 3))]
    return xs, ys


def _center_node(xs: list[int], ys: list[int], w: int, h: int) -> tuple[int, int]:
    x = min(xs, key=lambda v: abs(v - w // 2))
    y = min(ys, key=lambda v: abs(v - h // 2))
    return x, y


def _far_path_cell(grid: list[list[int]], start: tuple[int, int], rng: random.Random) -> tuple[int, int]:
    h = len(grid)
    w = len(grid[0])
    dist = {start: 0}
    q: deque[tuple[int, int]] = deque([start])
    while q:
        c, r = q.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nc = c + dc
            nr = r + dr
            nxt = (nc, nr)
            if 0 <= nc < w and 0 <= nr < h and grid[nr][nc] == FLOOR and nxt not in dist:
                dist[nxt] = dist[(c, r)] + 1
                q.append(nxt)

    if not dist:
        return start
    maxd = max(dist.values())
    far = [cell for cell, d in dist.items() if d >= maxd - ROAD_W * 2]
    return rng.choice(far)


def _dig_maze(
    grid: list[list[int]],
    xs: list[int],
    ys: list[int],
    start: tuple[int, int],
    rng: random.Random,
) -> _Meta:
    h = len(grid)
    w = len(grid[0])
    for r in range(h):
        for c in range(w):
            grid[r][c] = WALL

    sx = xs.index(start[0])
    sy = ys.index(start[1])
    seen = {(sx, sy)}
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    stack: list[tuple[int, int, tuple[int, int] | None]] = [(sx, sy, None)]
    _brush(grid, start[0], start[1], ROAD_W)

    while stack:
        xi, yi, prev = stack[-1]
        nxt = _next_node(xi, yi, prev, len(xs), len(ys), seen, rng)
        if nxt is None:
            stack.pop()
            continue

        nx, ny, step = nxt
        a = (xs[xi], ys[yi])
        b = (xs[nx], ys[ny])
        _carve_line(grid, a, b, ROAD_W)
        seen.add((nx, ny))
        edges.add(_edge_key((xi, yi), (nx, ny)))
        stack.append((nx, ny, step))

    return _Meta(xs, ys, edges)


def _next_node(
    xi: int,
    yi: int,
    prev: tuple[int, int] | None,
    w: int,
    h: int,
    seen: set[tuple[int, int]],
    rng: random.Random,
) -> tuple[int, int, tuple[int, int]] | None:
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    rng.shuffle(dirs)
    if prev is not None and rng.random() < DIR_BIAS:
        dirs = [prev, *[d for d in dirs if d != prev]]

    for dx, dy in dirs:
        nx = xi + dx
        ny = yi + dy
        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
            return nx, ny, (dx, dy)
    return None


def _open_loops(grid: list[list[int]], meta: _Meta, rng: random.Random) -> None:
    cand: list[tuple[tuple[int, int], tuple[int, int]]] = []
    gw = len(meta.xs)
    gh = len(meta.ys)
    for yi in range(gh):
        for xi in range(gw):
            for dx, dy in ((1, 0), (0, 1)):
                nx = xi + dx
                ny = yi + dy
                if nx >= gw or ny >= gh:
                    continue
                key = _edge_key((xi, yi), (nx, ny))
                if key not in meta.edges:
                    cand.append(((xi, yi), (nx, ny)))

    rng.shuffle(cand)
    limit = max(3, int(len(meta.edges) * LOOP_RATE))
    for ai, bi in cand[:limit]:
        a = (meta.xs[ai[0]], meta.ys[ai[1]])
        b = (meta.xs[bi[0]], meta.ys[bi[1]])
        _carve_line(grid, a, b, ROAD_W)
        meta.edges.add(_edge_key(ai, bi))


def _clear_start(grid: list[list[int]], start: tuple[int, int]) -> None:
    c, r = start
    rad = max(2, ROAD_W)
    for rr in range(r - rad, r + rad + 1):
        for cc in range(c - rad, c + rad + 1):
            if 1 <= cc < len(grid[0]) - 1 and 1 <= rr < len(grid) - 1:
                grid[rr][cc] = FLOOR


def _carve_line(grid: list[list[int]], a: tuple[int, int], b: tuple[int, int], width: int) -> None:
    ax, ay = a
    bx, by = b
    if ax == bx:
        y0, y1 = sorted((ay, by))
        for y in range(y0, y1 + 1):
            _brush(grid, ax, y, width)
    else:
        x0, x1 = sorted((ax, bx))
        for x in range(x0, x1 + 1):
            _brush(grid, x, ay, width)


def _brush(grid: list[list[int]], c: int, r: int, width: int) -> None:
    rad = max(0, width // 2)
    for rr in range(r - rad, r + rad + 1):
        for cc in range(c - rad, c + rad + 1):
            if 1 <= cc < len(grid[0]) - 1 and 1 <= rr < len(grid) - 1:
                grid[rr][cc] = FLOOR


def _edge_key(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return (a, b) if a <= b else (b, a)


class _Grid:
    def __init__(self, grid: list[list[int]]) -> None:
        self.grid = grid
        self.h = len(grid)
        self.w = len(grid[0])

    def walk(self, c: int, r: int) -> bool:
        return 0 <= c < self.w and 0 <= r < self.h and self.grid[r][c] == FLOOR

    def is_wall(self, c: int, r: int) -> bool:
        return not self.walk(c, r)
