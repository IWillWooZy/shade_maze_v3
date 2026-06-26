from collections import defaultdict
from typing import Any, Callable, DefaultDict


class Bus:
    def __init__(self) -> None:
        self._map: DefaultDict[str, list[Callable[..., None]]] = defaultdict(list)

    def on(self, name: str, fn: Callable[..., None]) -> None:
        if fn not in self._map[name]:
            self._map[name].append(fn)

    def off(self, name: str, fn: Callable[..., None]) -> None:
        if fn in self._map[name]:
            self._map[name].remove(fn)

    def emit(self, name: str, *args: Any, **kwargs: Any) -> None:
        for fn in tuple(self._map[name]):
            fn(*args, **kwargs)
