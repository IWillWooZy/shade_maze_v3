import time
import tkinter as tk

from .cfg import FIXED_DT, MAX_FRAME, SCREEN_H, SCREEN_W
from .entities import GameState
from .render import Renderer
from .systems import enemy_sys, anim_sys, buy_skill, choose_weapon, cleanup_sys, input_sys, logic_sys, move_sys
from .world import World


class Input:
    def __init__(self, root: tk.Tk) -> None:
        self.keys: set[str] = set()
        self.hit: set[str] = set()
        root.bind("<KeyPress>", self._press)
        root.bind("<KeyRelease>", self._release)

    def down(self, *names: str) -> bool:
        return any(n.lower() in self.keys for n in names)

    def take(self, *names: str) -> bool:
        names = {n.lower() for n in names}
        if self.hit & names:
            self.hit -= names
            return True
        return False

    def end_frame(self) -> None:
        self.hit.clear()

    def _press(self, e: tk.Event) -> None:
        for name in self._names(e):
            if name not in self.keys:
                self.hit.add(name)
            self.keys.add(name)

    def _release(self, e: tk.Event) -> None:
        for name in self._names(e):
            self.keys.discard(name)

    def _names(self, e: tk.Event) -> set[str]:
        res = set()
        key = str(e.keysym).lower()
        if key:
            res.add(key)
        ch = str(getattr(e, "char", "")).lower()
        if ch and ch.isprintable():
            res.add(ch)
        alt = {
            "return": "enter",
            "kp_enter": "enter",
            "space": "space",
            "escape": "esc",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
            "ц": "w",
            "ф": "a",
            "ы": "s",
            "в": "d",
            "з": "p",
            "к": "r",
            "у": "e",
            "й": "q",
            "ш": "i",
            "п": "g",
            "а": "f",
            "shift_l": "shift",
            "shift_r": "shift",
        }
        for v in list(res):
            if v in alt:
                res.add(alt[v])
        return res


class Game:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Лабиринт искр")
        self.root.resizable(False, False)
        self.cv = tk.Canvas(self.root, width=SCREEN_W, height=SCREEN_H, highlightthickness=0)
        self.cv.pack()
        self.inp = Input(self.root)
        self.world = World.new()
        self.view = Renderer(self.cv)
        self.last = time.perf_counter()
        self.acc = 0.0
        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        self.loop()
        self.root.mainloop()

    def close(self) -> None:
        self.closed = True
        self.root.destroy()

    def loop(self) -> None:
        if self.closed:
            return
        now = time.perf_counter()
        frame = min(now - self.last, MAX_FRAME)
        self.last = now
        self.world.add_fps(frame)

        self._keys()
        if self.world.state is GameState.PLAY:
            self.acc += frame * self.world.time_scale
            steps = 0
            while self.acc >= FIXED_DT and steps < 8:
                self._fixed(FIXED_DT)
                self.acc -= FIXED_DT
                steps += 1
                if self.world.state is not GameState.PLAY:
                    self.acc = 0.0
                    break
        else:
            self.acc = 0.0

        self.view.draw(self.world, frame)
        self.inp.end_frame()
        self.root.after(1, self.loop)

    def _fixed(self, dt: float) -> None:
        input_sys(self.world, self.inp, dt)
        enemy_sys(self.world, dt)
        move_sys(self.world, dt)
        logic_sys(self.world, dt)
        anim_sys(self.world, dt)
        cleanup_sys(self.world)

    def _keys(self) -> None:
        w = self.world
        if self.inp.take("f1"):
            w.debug = not w.debug

        if w.state is GameState.MENU:
            if self.inp.take("enter", "return"):
                w.reset_run()
                self.acc = 0.0
            elif self.inp.take("esc", "escape"):
                self.close()
            return

        if w.state is GameState.PLAY:
            if self.inp.take("i", "tab", "g"):
                w.state = GameState.INV
            elif self.inp.take("p", "esc", "escape"):
                w.state = GameState.PAUSE
            elif self.inp.take("r"):
                w.reset_run()
                self.acc = 0.0
            elif self.inp.take("f2"):
                w.time_scale = 0.25
                w.bus.emit("note", "Замедление x0.25", 1.2)
            elif self.inp.take("f3"):
                w.time_scale = 1.0
                w.bus.emit("note", "Обычная скорость", 1.2)
            return

        if w.state is GameState.INV:
            if self.inp.take("i", "tab", "g", "esc", "escape"):
                w.state = GameState.PLAY
            elif self.inp.take("1"):
                choose_weapon(w, 0)
            elif self.inp.take("2"):
                choose_weapon(w, 1)
            elif self.inp.take("3"):
                choose_weapon(w, 2)
            elif self.inp.take("4"):
                buy_skill(w, "spd")
            elif self.inp.take("5"):
                buy_skill(w, "pow")
            elif self.inp.take("6"):
                buy_skill(w, "vit")
            elif self.inp.take("7"):
                buy_skill(w, "dash")
            elif self.inp.take("8"):
                buy_skill(w, "rage")
            elif self.inp.take("9"):
                buy_skill(w, "mag")
            return

        if w.state is GameState.PAUSE:
            if self.inp.take("p", "esc", "escape"):
                w.state = GameState.PLAY
            elif self.inp.take("r"):
                w.reset_run()
                self.acc = 0.0
            return

        if w.state in (GameState.WIN, GameState.LOSE):
            if self.inp.take("enter", "return", "r"):
                w.reset_run()
                self.acc = 0.0
            elif self.inp.take("esc", "escape"):
                w.state = GameState.MENU
