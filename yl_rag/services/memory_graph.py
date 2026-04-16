import atexit
import os
import pickle
import threading
import time

import networkx as nx


class MemoryGraph:
    def __init__(self, path="./cache/memory_graph.pkl"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.graph = nx.DiGraph()
        self.lock = threading.Lock()

        self.needs_save = False
        self._load()

        # 启动后台守护线程进行持久化，防止阻塞主业务流
        self.save_thread = threading.Thread(target=self._background_save, daemon=True)
        self.save_thread.start()

        # 注册优雅停机钩子，防止数据丢失
        atexit.register(self._force_save)

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "rb") as f:
                    self.graph = pickle.load(f)
            except Exception:
                self.graph = nx.DiGraph()

    def _background_save(self):
        while True:
            time.sleep(10)  # 每10秒检查一次写盘需求
            if self.needs_save:
                self._force_save()

    def _force_save(self):
        with self.lock:
            if not self.needs_save:
                return
            temp_path = self.path + ".tmp"
            # 使用临时文件 + 原子替换，防止写入中断导致文件损坏
            with open(temp_path, "wb") as f:
                pickle.dump(self.graph, f)
            os.replace(temp_path, self.path)
            self.needs_save = False

    def add_memory(self, doc_id: str, tags: list, room: str):
        with self.lock:
            self.graph.add_node(doc_id, type="memory", room=room)
            if not self.graph.has_node(room):
                self.graph.add_node(room, type="room")
            self.graph.add_edge(doc_id, room, relation="located_in")

            for tag in tags:
                if not self.graph.has_node(tag):
                    self.graph.add_node(tag, type="tag")
                self.graph.add_edge(doc_id, tag, relation="about")

            self.needs_save = True  # 仅标记，由后台线程处理 IO


memory_graph = MemoryGraph()
