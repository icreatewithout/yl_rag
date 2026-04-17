from __future__ import annotations

import atexit
import pickle
import threading
import time
from pathlib import Path

import networkx as nx


class MemoryGraph:
    """In-memory relation graph with periodic persistence."""

    def __init__(self, path: str = "./cache/memory_graph.pkl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = nx.DiGraph()
        self.lock = threading.Lock()
        self.needs_save = False
        self._load()
        self.save_thread = threading.Thread(target=self._background_save, daemon=True)
        self.save_thread.start()
        atexit.register(self._force_save)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("rb") as file:
                self.graph = pickle.load(file)  # noqa: S301
        except Exception:
            self.graph = nx.DiGraph()

    def _background_save(self) -> None:
        while True:
            time.sleep(10)
            if self.needs_save:
                self._force_save()

    def _force_save(self) -> None:
        with self.lock:
            if not self.needs_save:
                return
            temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            with temp_path.open("wb") as file:
                pickle.dump(self.graph, file)
            temp_path.replace(self.path)
            self.needs_save = False

    def add_memory(self, doc_id: str, tags: list[str], room: str) -> None:
        """Add one memory node and connect it to room/tag nodes."""
        with self.lock:
            self.graph.add_node(doc_id, type="memory", room=room)
            if not self.graph.has_node(room):
                self.graph.add_node(room, type="room")
            self.graph.add_edge(doc_id, room, relation="located_in")
            for tag in tags:
                if not self.graph.has_node(tag):
                    self.graph.add_node(tag, type="tag")
                self.graph.add_edge(doc_id, tag, relation="about")
            self.needs_save = True


memory_graph = MemoryGraph()
