from pathlib import Path

from yl_rag.services.memory_graph import MemoryGraph


def test_memory_graph_score_prefers_tag_match(tmp_path: Path) -> None:
    """Graph score should prioritize memories whose tags match the query."""
    graph = MemoryGraph(path=str(tmp_path / "memory_graph.pkl"))

    graph.add_memory("doc_a", ["宇哥", "出差", "上海"], "yu_ge")
    graph.add_memory("doc_b", ["宇哥", "购物", "键盘"], "yu_ge")

    score_a = graph.graph_score("doc_a", room="yu_ge", query="宇哥出差安排")
    score_b = graph.graph_score("doc_b", room="yu_ge", query="宇哥出差安排")

    assert score_a > score_b
