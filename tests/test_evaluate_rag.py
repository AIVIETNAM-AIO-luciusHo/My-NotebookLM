"""
Unit tests for src/evaluate_rag.py — Phase 4 RAGAS Evaluation Benchmark.

Strategy
--------
All heavy dependencies (ChatOllama, HuggingFaceEmbeddings, ragas.evaluate)
are mocked so the test suite runs in milliseconds without downloading any
model weights or requiring Ollama to be running.

The tests assert:
  1. The mock pipeline helpers produce the expected data types.
  2. _build_critic_models() wires up LangchainLLMWrapper / LangchainEmbeddingsWrapper
     with the correct model names.
  3. run_evaluation() correctly constructs a HuggingFace Dataset
     (right column names, right column types) before calling evaluate().
  4. run_evaluation() returns a pandas DataFrame and writes the CSV report.
  5. run_evaluation() raises ValueError for an empty qa_pairs list.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build a minimal fake RAGAS result that mimics ragas.Result
# ─────────────────────────────────────────────────────────────────────────────

def _make_fake_result(n_samples: int = 2) -> MagicMock:
    """Return a MagicMock that behaves like a ragas.Result object."""
    fake_df = pd.DataFrame(
        {
            "question": [f"q{i}" for i in range(n_samples)],
            "answer": [f"a{i}" for i in range(n_samples)],
            "contexts": [[f"ctx{i}"] for i in range(n_samples)],
            "ground_truth": [f"gt{i}" for i in range(n_samples)],
            "faithfulness": [0.85] * n_samples,
            "answer_relevancy": [0.90] * n_samples,
            "context_precision": [0.80] * n_samples,
        }
    )
    result_mock = MagicMock()
    result_mock.to_pandas.return_value = fake_df
    return result_mock


# ─────────────────────────────────────────────────────────────────────────────
# Test — mock pipeline helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestMockPipelineHelpers(unittest.TestCase):
    """Tests for the placeholder retrieval / generation hooks."""

    def setUp(self) -> None:
        # evaluate_rag may already be cached; reload fresh
        if "evaluate_rag" in sys.modules:
            del sys.modules["evaluate_rag"]
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    def test_mock_retrieve_contexts_returns_list_of_strings(self) -> None:
        from evaluate_rag import _mock_retrieve_contexts

        result = _mock_retrieve_contexts("What is BCNF?")
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for ctx in result:
            self.assertIsInstance(ctx, str)

    def test_mock_generate_answer_returns_string(self) -> None:
        from evaluate_rag import _mock_generate_answer

        answer = _mock_generate_answer("What is BCNF?", ["Context A", "Context B"])
        self.assertIsInstance(answer, str)
        self.assertGreater(len(answer), 0)

    def test_mock_retrieve_contexts_includes_question(self) -> None:
        from evaluate_rag import _mock_retrieve_contexts

        question = "unique_marker_xyz"
        contexts = _mock_retrieve_contexts(question)
        self.assertTrue(any(question in ctx for ctx in contexts))


# ─────────────────────────────────────────────────────────────────────────────
# Test — _build_critic_models
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCriticModels(unittest.TestCase):
    """Verifies that _build_critic_models wires up the correct model identifiers."""

    def setUp(self) -> None:
        if "evaluate_rag" in sys.modules:
            del sys.modules["evaluate_rag"]
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    @patch("langchain_ollama.ChatOllama")
    @patch("langchain_huggingface.HuggingFaceEmbeddings")
    @patch("ragas.llms.LangchainLLMWrapper")
    @patch("ragas.embeddings.LangchainEmbeddingsWrapper")
    def test_uses_correct_llm_model_name(
        self,
        mock_emb_wrapper: MagicMock,
        mock_llm_wrapper: MagicMock,
        mock_hf_emb: MagicMock,
        mock_chat_ollama: MagicMock,
    ) -> None:
        from evaluate_rag import _build_critic_models

        _build_critic_models()

        mock_chat_ollama.assert_called_once()
        kwargs: dict[str, Any] = mock_chat_ollama.call_args.kwargs
        self.assertEqual(kwargs.get("model"), "llama3.2")

    @patch("langchain_ollama.ChatOllama")
    @patch("langchain_huggingface.HuggingFaceEmbeddings")
    @patch("ragas.llms.LangchainLLMWrapper")
    @patch("ragas.embeddings.LangchainEmbeddingsWrapper")
    def test_uses_correct_embedding_model_name(
        self,
        mock_emb_wrapper: MagicMock,
        mock_llm_wrapper: MagicMock,
        mock_hf_emb: MagicMock,
        mock_chat_ollama: MagicMock,
    ) -> None:
        from evaluate_rag import _build_critic_models

        _build_critic_models()

        mock_hf_emb.assert_called_once()
        kwargs = mock_hf_emb.call_args.kwargs
        self.assertEqual(kwargs.get("model_name"), "keepitreal/vietnamese-sbert")

    @patch("langchain_ollama.ChatOllama")
    @patch("langchain_huggingface.HuggingFaceEmbeddings")
    @patch("ragas.llms.LangchainLLMWrapper")
    @patch("ragas.embeddings.LangchainEmbeddingsWrapper")
    def test_returns_wrapped_models(
        self,
        mock_emb_wrapper: MagicMock,
        mock_llm_wrapper: MagicMock,
        mock_hf_emb: MagicMock,
        mock_chat_ollama: MagicMock,
    ) -> None:
        from evaluate_rag import _build_critic_models

        llm, emb = _build_critic_models()

        # The returned objects must be the wrapper instances, not raw models
        self.assertIs(llm, mock_llm_wrapper.return_value)
        self.assertIs(emb, mock_emb_wrapper.return_value)


# ─────────────────────────────────────────────────────────────────────────────
# Test — run_evaluation: dataset construction
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEvaluationDatasetConstruction(unittest.TestCase):
    """
    Verifies that run_evaluation formats data into the correct HuggingFace
    Dataset schema before calling ragas.evaluate.
    """

    _QA_PAIRS = [
        {
            "question": "What is 2NF?",
            "ground_truth": "2NF eliminates partial dependencies.",
        },
        {
            "question": "Define a functional dependency.",
            "ground_truth": "X → Y means X uniquely determines Y.",
        },
    ]

    def setUp(self) -> None:
        if "evaluate_rag" in sys.modules:
            del sys.modules["evaluate_rag"]
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    def test_dataset_has_required_columns(
        self,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """The Dataset must contain question, answer, contexts, ground_truth."""
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()  # fake Dataset

        from evaluate_rag import run_evaluation

        with patch("builtins.open", unittest.mock.mock_open()):
            run_evaluation(self._QA_PAIRS)

        # Inspect what was passed to Dataset.from_list
        mock_from_list.assert_called_once()
        rows: list[dict] = mock_from_list.call_args.args[0]

        self.assertEqual(len(rows), len(self._QA_PAIRS))
        required_keys = {"question", "answer", "contexts", "ground_truth"}
        for row in rows:
            self.assertEqual(set(row.keys()), required_keys)

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    def test_contexts_column_is_list_of_strings(
        self,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """contexts must be list[str] — RAGAS rejects a plain string."""
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        with patch("builtins.open", unittest.mock.mock_open()):
            run_evaluation(self._QA_PAIRS)

        rows: list[dict] = mock_from_list.call_args.args[0]
        for row in rows:
            self.assertIsInstance(row["contexts"], list)
            for ctx in row["contexts"]:
                self.assertIsInstance(ctx, str)

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    def test_questions_and_ground_truths_preserved(
        self,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """question and ground_truth must flow through unchanged from qa_pairs."""
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        with patch("builtins.open", unittest.mock.mock_open()):
            run_evaluation(self._QA_PAIRS)

        rows: list[dict] = mock_from_list.call_args.args[0]
        for original, row in zip(self._QA_PAIRS, rows):
            self.assertEqual(row["question"], original["question"])
            self.assertEqual(row["ground_truth"], original["ground_truth"])


# ─────────────────────────────────────────────────────────────────────────────
# Test — run_evaluation: output DataFrame
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEvaluationOutput(unittest.TestCase):
    """Verifies that run_evaluation returns a DataFrame and writes the CSV."""

    _QA_PAIRS = [
        {"question": "What is ACID?", "ground_truth": "Atomicity, Consistency, Isolation, Durability."},
    ]

    def setUp(self) -> None:
        if "evaluate_rag" in sys.modules:
            del sys.modules["evaluate_rag"]
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_returns_dataframe(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_build.return_value = (MagicMock(), MagicMock())
        fake_result = _make_fake_result(1)
        mock_evaluate.return_value = fake_result
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        result = run_evaluation(self._QA_PAIRS)

        self.assertIsInstance(result, pd.DataFrame)

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_dataframe_contains_metric_columns(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_build.return_value = (MagicMock(), MagicMock())
        fake_result = _make_fake_result(1)
        mock_evaluate.return_value = fake_result
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        df = run_evaluation(self._QA_PAIRS)

        expected_metrics = {"faithfulness", "answer_relevancy", "context_precision"}
        self.assertTrue(expected_metrics.issubset(set(df.columns)))

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_csv_export_is_called(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_evaluate.return_value = _make_fake_result(1)
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        run_evaluation(self._QA_PAIRS)

        mock_to_csv.assert_called_once()
        # Verify index=False is passed (no spurious row numbers in CSV)
        _, kwargs = mock_to_csv.call_args
        self.assertFalse(kwargs.get("index", True))

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    def test_empty_qa_pairs_raises_value_error(
        self,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_build.return_value = (MagicMock(), MagicMock())

        from evaluate_rag import run_evaluation

        with self.assertRaises(ValueError):
            run_evaluation([])


# ─────────────────────────────────────────────────────────────────────────────
# Test — RAGAS evaluate is called with correct arguments
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEvaluationCallsEvaluate(unittest.TestCase):
    """Verifies the arguments passed to ragas.evaluate."""

    _QA_PAIRS = [
        {"question": "Define SELECT in RA.", "ground_truth": "σ filters rows by predicate."},
        {"question": "Define PROJECT in RA.", "ground_truth": "π extracts columns."},
    ]

    def setUp(self) -> None:
        if "evaluate_rag" in sys.modules:
            del sys.modules["evaluate_rag"]
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_evaluate_called_once(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_llm = MagicMock(name="critic_llm")
        mock_emb = MagicMock(name="critic_emb")
        mock_build.return_value = (mock_llm, mock_emb)
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        run_evaluation(self._QA_PAIRS)

        mock_evaluate.assert_called_once()

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_evaluate_receives_three_metrics(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_build.return_value = (MagicMock(), MagicMock())
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        run_evaluation(self._QA_PAIRS)

        _, kwargs = mock_evaluate.call_args
        metrics = kwargs.get("metrics") or mock_evaluate.call_args.args[1]
        self.assertEqual(len(metrics), 3)

    @patch("evaluate_rag._build_critic_models")
    @patch("ragas.evaluate")
    @patch("datasets.Dataset.from_list")
    @patch("pandas.DataFrame.to_csv")
    def test_evaluate_receives_local_llm_and_embeddings(
        self,
        mock_to_csv: MagicMock,
        mock_from_list: MagicMock,
        mock_evaluate: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        mock_llm = MagicMock(name="critic_llm")
        mock_emb = MagicMock(name="critic_emb")
        mock_build.return_value = (mock_llm, mock_emb)
        mock_evaluate.return_value = _make_fake_result(len(self._QA_PAIRS))
        mock_from_list.return_value = MagicMock()

        from evaluate_rag import run_evaluation

        run_evaluation(self._QA_PAIRS)

        _, kwargs = mock_evaluate.call_args
        self.assertIs(kwargs.get("llm"), mock_llm)
        self.assertIs(kwargs.get("embeddings"), mock_emb)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
