"""
Unit tests for the Hybrid GraphRAG pipeline in src/backend.py.

Strategy
--------
All Ollama calls (triplet extraction, entity extraction, generation) are
mocked so the suite runs in milliseconds, fully offline, with no model
weights loaded.  `langchain_huggingface` is force-mocked *before* backend
is imported so the module-level HuggingFaceEmbeddings singleton never
touches real weights.

The tests assert:
  1. _parse_triplets() handles well-formed, malformed, and NONE outputs.
  2. _extract_triplets_from_chunk() uses a deterministic LLM (temperature=0.0)
     and degrades to [] when Ollama is unreachable.
  3. _ingest_chunks_into_graph() populates nodes/edges (with lowercase-key
     dedup and relation merging) from sample text.
  4. _save_graph() / _load_graph() round-trip through knowledge_graph.graphml.
  5. _get_graph_context() returns 1–2 hop triplet facts for matched entities
     and [] when the graph is empty or nothing matches.
  6. _build_hybrid_context() correctly fuses vector chunks with graph triplets.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Import backend with heavy dependencies neutralised
# ─────────────────────────────────────────────────────────────────────────────

# Must happen BEFORE `import backend`: the module instantiates
# HuggingFaceEmbeddings at import time, which would load model weights.
sys.modules["langchain_huggingface"] = MagicMock(name="langchain_huggingface")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import backend  # noqa: E402


def _mock_ollama_returning(text: str) -> MagicMock:
    """An Ollama class mock whose instances return *text* from invoke()."""
    instance = MagicMock()
    instance.invoke.return_value = text
    return MagicMock(return_value=instance)


@pytest.fixture()
def fresh_graph(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> nx.DiGraph:
    """Give each test an isolated empty graph and a graphml path in tmp_path."""
    graph = nx.DiGraph()
    monkeypatch.setattr(backend, "_knowledge_graph", graph)
    monkeypatch.setattr(backend, "GRAPH_PATH", tmp_path / "knowledge_graph.graphml")
    return graph


# ─────────────────────────────────────────────────────────────────────────────
# 1. Triplet parsing
# ─────────────────────────────────────────────────────────────────────────────


class TestParseTriplets:
    def test_parses_well_formed_lines(self) -> None:
        raw = (
            "(Marie Curie, discovered, polonium)\n"
            "( Marie Curie ,  discovered , radium )\n"
            "(Marie Curie, professor at, University of Paris)"
        )
        assert backend._parse_triplets(raw) == [
            ("Marie Curie", "discovered", "polonium"),
            ("Marie Curie", "discovered", "radium"),
            ("Marie Curie", "professor at", "University of Paris"),
        ]

    def test_none_sentinel_yields_empty_list(self) -> None:
        assert backend._parse_triplets("NONE") == []
        assert backend._parse_triplets("  none \n") == []
        assert backend._parse_triplets("") == []

    def test_malformed_lines_are_skipped(self) -> None:
        raw = (
            "Here are the triplets:\n"
            "(only two, parts)\n"
            "(A, rel, B)\n"
            "not a triplet at all\n"
            "(too, many, parts, here)"
        )
        result = backend._parse_triplets(raw)
        assert ("A", "rel", "B") in result
        assert ("only two", "parts") not in result
        assert all(len(t) == 3 for t in result)

    def test_collapses_internal_whitespace(self) -> None:
        assert backend._parse_triplets("(Marie   Curie, works\tat, Paris)") == [
            ("Marie Curie", "works at", "Paris")
        ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. LLM triplet extraction (mocked Ollama)
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractTriplets:
    def test_uses_deterministic_llm_and_parses_output(self) -> None:
        ollama_cls = _mock_ollama_returning("(Ollama, runs, llama3.2)")
        with patch.object(backend, "Ollama", ollama_cls):
            result = backend._extract_triplets_from_chunk("Ollama runs llama3.2.")

        assert result == [("Ollama", "runs", "llama3.2")]
        ollama_cls.assert_called_once_with(model="llama3.2", temperature=0.0)
        prompt_sent = ollama_cls.return_value.invoke.call_args[0][0]
        assert "Ollama runs llama3.2." in prompt_sent

    def test_returns_empty_list_when_ollama_fails(self) -> None:
        ollama_cls = MagicMock()
        ollama_cls.return_value.invoke.side_effect = ConnectionError("Ollama down")
        with patch.object(backend, "Ollama", ollama_cls):
            assert backend._extract_triplets_from_chunk("any text") == []

    def test_returns_empty_list_for_none_output(self) -> None:
        with patch.object(backend, "Ollama", _mock_ollama_returning("NONE")):
            assert backend._extract_triplets_from_chunk("gibberish") == []


# ─────────────────────────────────────────────────────────────────────────────
# 3. Graph ingestion
# ─────────────────────────────────────────────────────────────────────────────


class TestGraphIngestion:
    def test_populates_nodes_and_edges_from_sample_text(self, fresh_graph: nx.DiGraph) -> None:
        llm_output = (
            "(Marie Curie, discovered, polonium)\n"
            "(Marie Curie, professor at, University of Paris)"
        )
        with patch.object(backend, "Ollama", _mock_ollama_returning(llm_output)):
            added = backend._ingest_chunks_into_graph(
                fresh_graph, ["Marie Curie discovered polonium..."], source="curie.pdf"
            )

        assert added == 2
        assert fresh_graph.number_of_nodes() == 3
        assert fresh_graph.has_edge("marie curie", "polonium")
        assert fresh_graph["marie curie"]["polonium"]["relation"] == "discovered"
        assert fresh_graph["marie curie"]["polonium"]["source"] == "curie.pdf"
        # Original casing preserved as display label
        assert fresh_graph.nodes["marie curie"]["label"] == "Marie Curie"

    def test_merges_duplicate_edges_and_distinct_relations(self, fresh_graph: nx.DiGraph) -> None:
        llm_output = "(A, teaches, B)\n(A, teaches, B)\n(A, mentors, B)"
        with patch.object(backend, "Ollama", _mock_ollama_returning(llm_output)):
            added = backend._ingest_chunks_into_graph(fresh_graph, ["chunk"], source="x.pdf")

        assert added == 1  # one physical edge
        assert fresh_graph["a"]["b"]["relation"] == "teaches; mentors"

    def test_self_loops_are_rejected(self, fresh_graph: nx.DiGraph) -> None:
        with patch.object(backend, "Ollama", _mock_ollama_returning("(A, equals, A)")):
            added = backend._ingest_chunks_into_graph(fresh_graph, ["chunk"], source="x.pdf")
        assert added == 0
        assert fresh_graph.number_of_edges() == 0

    def test_failed_chunk_does_not_abort_ingestion(self, fresh_graph: nx.DiGraph) -> None:
        ollama_cls = MagicMock()
        instance = ollama_cls.return_value
        instance.invoke.side_effect = [ConnectionError("boom"), "(A, rel, B)"]
        with patch.object(backend, "Ollama", ollama_cls):
            added = backend._ingest_chunks_into_graph(
                fresh_graph, ["bad chunk", "good chunk"], source="x.pdf"
            )
        assert added == 1
        assert fresh_graph.has_edge("a", "b")


# ─────────────────────────────────────────────────────────────────────────────
# 4. GraphML persistence
# ─────────────────────────────────────────────────────────────────────────────


class TestGraphPersistence:
    def test_save_and_load_round_trip(self, fresh_graph: nx.DiGraph) -> None:
        fresh_graph.add_node("marie curie", label="Marie Curie")
        fresh_graph.add_node("polonium", label="polonium")
        fresh_graph.add_edge("marie curie", "polonium", relation="discovered", source="curie.pdf")

        assert backend._save_graph(fresh_graph) is True
        assert backend.GRAPH_PATH.exists()

        loaded = backend._load_graph()
        assert isinstance(loaded, nx.DiGraph)
        assert set(loaded.nodes) == {"marie curie", "polonium"}
        assert loaded["marie curie"]["polonium"]["relation"] == "discovered"

    def test_load_missing_file_returns_empty_graph(self, tmp_path: Path) -> None:
        loaded = backend._load_graph(tmp_path / "does_not_exist.graphml")
        assert isinstance(loaded, nx.DiGraph)
        assert loaded.number_of_nodes() == 0

    def test_load_corrupt_file_returns_empty_graph(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.graphml"
        corrupt.write_text("this is not graphml <<<")
        loaded = backend._load_graph(corrupt)
        assert loaded.number_of_nodes() == 0

    def test_save_failure_returns_false(self, fresh_graph: nx.DiGraph, tmp_path: Path) -> None:
        bad_path = tmp_path / "no_such_dir" / "graph.graphml"
        assert backend._save_graph(fresh_graph, bad_path) is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. Graph sub-pipeline retrieval
# ─────────────────────────────────────────────────────────────────────────────


def _build_sample_graph() -> nx.DiGraph:
    """marie curie → polonium → radioactivity, plus an unrelated island."""
    g = nx.DiGraph()
    g.add_node("marie curie", label="Marie Curie")
    g.add_node("polonium", label="polonium")
    g.add_node("radioactivity", label="radioactivity")
    g.add_node("unrelated", label="unrelated")
    g.add_edge("marie curie", "polonium", relation="discovered")
    g.add_edge("polonium", "radioactivity", relation="exhibits")
    return g


class TestGraphRetrieval:
    def test_returns_one_and_two_hop_facts_for_matched_entity(self) -> None:
        graph = _build_sample_graph()
        with patch.object(backend, "_extract_query_entities", return_value=["Marie Curie"]):
            facts = backend._get_graph_context(graph, "Who is Marie Curie?")

        assert "(Marie Curie, discovered, polonium)" in facts
        # 2-hop expansion through the polonium neighbour
        assert "(polonium, exhibits, radioactivity)" in facts

    def test_empty_graph_returns_no_facts(self) -> None:
        assert backend._get_graph_context(nx.DiGraph(), "anything") == []

    def test_no_matching_entities_returns_no_facts(self) -> None:
        graph = _build_sample_graph()
        with patch.object(backend, "_extract_query_entities", return_value=["quasar"]):
            assert backend._get_graph_context(graph, "What is a quasar?") == []

    def test_max_facts_cap_is_respected(self) -> None:
        graph = nx.DiGraph()
        for i in range(30):
            graph.add_edge("hub", f"leaf{i}", relation="links")
        with patch.object(backend, "_extract_query_entities", return_value=["hub"]):
            facts = backend._get_graph_context(graph, "hub?", max_facts=5)
        assert len(facts) == 5

    def test_entity_extraction_falls_back_to_keywords_on_llm_failure(self) -> None:
        ollama_cls = MagicMock()
        ollama_cls.return_value.invoke.side_effect = ConnectionError("Ollama down")
        with patch.object(backend, "Ollama", ollama_cls):
            entities = backend._extract_query_entities("Marie Curie và polonium là gì?")
        assert "marie" in entities
        assert "polonium" in entities
        assert "là" not in entities  # short tokens filtered out


# ─────────────────────────────────────────────────────────────────────────────
# 6. Context fusion
# ─────────────────────────────────────────────────────────────────────────────


class TestHybridContextFusion:
    def test_fuses_chunks_and_graph_facts(self) -> None:
        context = backend._build_hybrid_context(
            chunks=["Chunk one text.", "Chunk two text."],
            graph_facts=["(Marie Curie, discovered, polonium)"],
        )
        assert "Chunk one text." in context
        assert "Chunk two text." in context
        assert "- (Marie Curie, discovered, polonium)" in context
        assert "Vector Search" in context
        assert "Knowledge Graph" in context

    def test_no_graph_facts_yields_vector_only_context(self) -> None:
        context = backend._build_hybrid_context(chunks=["Only chunk."], graph_facts=[])
        assert "Only chunk." in context
        assert "Knowledge Graph" not in context

    def test_empty_inputs_yield_empty_string(self) -> None:
        assert backend._build_hybrid_context(chunks=[], graph_facts=[]) == ""
