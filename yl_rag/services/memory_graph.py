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

    @staticmethod
    def _tag_match_score(query: str, tag: str) -> float:
        query_l = query.lower().strip()
        tag_l = tag.lower().strip()
        if not query_l or not tag_l:
            return 0.0
        if tag_l in query_l:
            return 1.0
        query_words = set(query_l.split())
        tag_words = set(tag_l.split())
        if not query_words or not tag_words:
            return 0.0
        overlap = len(query_words & tag_words)
        return overlap / max(len(tag_words), 1)

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

    def get_memory_tags(self, doc_id: str) -> set[str]:
        """Return tags directly attached to one memory node."""
        with self.lock:
            if not self.graph.has_node(doc_id):
                return set()
            return {
                node
                for _, node, data in self.graph.out_edges(doc_id, data=True)
                if data.get("relation") == "about"
            }

    def graph_score(self, doc_id: str, room: str | None, query: str) -> float:
        """Calculate graph-based boost score for one memory item."""
        tags = self.get_memory_tags(doc_id)
        if not tags:
            return 0.0

        tag_scores = [self._tag_match_score(query, tag) for tag in tags]
        tag_score = sum(tag_scores) / max(len(tags), 1)
        room_bonus = 0.1 if room and self.graph.has_edge(doc_id, room) else 0.0
        return tag_score + room_bonus


memory_graph = MemoryGraph()
