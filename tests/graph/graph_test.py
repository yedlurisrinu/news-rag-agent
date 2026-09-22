"""
tests/graph/state_test.py

Unit tests for graph/state.py:
  - merge_article_hits — the four reducer-contract properties + behaviour
  - NewsState wiring    — reducer registered, output TypedDicts match state keys
"""
from __future__ import annotations

import copy
from typing import get_type_hints

import pytest
from langgraph.channels.binop import BinaryOperatorAggregate
from langgraph.graph import START, StateGraph

from graph.graph import (
    ArticleRef,
    CategoryOutput,
    NewsState,
    SearchOutput,
    SummaryOutput,
    merge_article_hits,
)


# The NewsState key that carries ArticleRefs. Change here only when you rename it.
ARTICLES_KEY = "articles"


def ref(article_id: str, score: float) -> ArticleRef:
    return {"article_id": article_id, "score": score}


A = [ref("id_1", 0.7), ref("id_2", 0.9)]
B = [ref("id_1", 0.8), ref("id_3", 0.5)]
EXPECTED_A_B = [ref("id_2", 0.9), ref("id_1", 0.8), ref("id_3", 0.5)]

# (current, update) pairs reused by the property tests
PAIRS = [
    pytest.param(A, B, id="overlap-update-higher"),
    pytest.param(B, A, id="overlap-update-lower"),
    pytest.param([ref("x", 0.5)], [ref("y", 0.5)], id="equal-scores-diff-ids"),
    pytest.param([ref("x", 0.5)], [ref("x", 0.5)], id="identical-refs"),
    pytest.param([], A, id="empty-current"),
    pytest.param(A, [], id="empty-update"),
]


# ---------------------------------------------------------------- 1. empty start
class TestEmptyStart:
    def test_both_empty_returns_empty(self):
        assert merge_article_hits([], []) == []

    def test_empty_on_either_side_gives_same_result(self):
        assert merge_article_hits([], A) == merge_article_hits(A, [])

    def test_empty_merge_normalises_order(self):
        unsorted = [ref("id_1", 0.7), ref("id_2", 0.9)]
        assert merge_article_hits([], unsorted) == [ref("id_2", 0.9), ref("id_1", 0.7)]


# ------------------------------------------------------------ 2. order-independent
class TestOrderIndependent:
    @pytest.mark.parametrize(("current", "update"), PAIRS)
    def test_swapping_arguments_gives_same_result(self, current, update):
        assert merge_article_hits(current, update) == merge_article_hits(update, current)

    def test_write_order_of_three_parallel_updates_does_not_matter(self):
        c = [ref("id_4", 0.8), ref("id_2", 0.95)]
        left = merge_article_hits(merge_article_hits(A, B), c)
        right = merge_article_hits(merge_article_hits(c, B), A)
        assert left == right


# ------------------------------------------------------------------ 3. idempotent
class TestIdempotent:
    @pytest.mark.parametrize(("current", "update"), PAIRS)
    def test_applying_same_update_twice_is_a_no_op(self, current, update):
        once = merge_article_hits(current, update)
        assert merge_article_hits(once, update) == once

    def test_merging_with_itself_equals_normalised_self(self):
        assert merge_article_hits(A, A) == merge_article_hits(A, [])


# ------------------------------------------------------------------------ 4. pure
class TestPure:
    @pytest.mark.parametrize(("current", "update"), PAIRS)
    def test_inputs_unchanged_after_call(self, current, update):
        current_before, update_before = copy.deepcopy(current), copy.deepcopy(update)
        merge_article_hits(current, update)
        assert current == current_before
        assert update == update_before

    def test_returns_a_new_list_not_an_input(self):
        result = merge_article_hits(A, B)
        assert result is not A
        assert result is not B

    def test_mutating_result_does_not_leak_into_inputs(self):
        # stricter than the contract: guards against aliasing with checkpoint snapshots
        current, update = copy.deepcopy(A), copy.deepcopy(B)
        result = merge_article_hits(current, update)
        result[0]["score"] = -1.0
        assert current == A
        assert update == B


# -------------------------------------------------------------------- behaviour
class TestBehaviour:
    def test_worked_example(self):
        assert merge_article_hits(A, B) == EXPECTED_A_B

    def test_higher_incoming_score_replaces(self):
        assert merge_article_hits([ref("id_1", 0.7)], [ref("id_1", 0.8)]) == [ref("id_1", 0.8)]

    def test_lower_incoming_score_is_ignored(self):
        assert merge_article_hits([ref("id_1", 0.8)], [ref("id_1", 0.7)]) == [ref("id_1", 0.8)]

    def test_duplicate_ids_within_one_update_keep_max(self):
        update = [ref("id_1", 0.3), ref("id_1", 0.9), ref("id_1", 0.6)]
        assert merge_article_hits([], update) == [ref("id_1", 0.9)]

    def test_each_id_appears_once(self):
        ids = [r["article_id"] for r in merge_article_hits(A, B)]
        assert len(ids) == len(set(ids))

    def test_sorted_by_score_desc_then_id_asc(self):
        # your self-check from the sorting discussion: id_0 and id_1 tie at 0.8
        update = [ref("id_1", 0.8), ref("id_2", 0.9), ref("id_3", 0.5), ref("id_0", 0.8)]
        assert [r["article_id"] for r in merge_article_hits([], update)] == ["id_2", "id_0", "id_1", "id_3"]


# ------------------------------------------------------------------- state wiring
def noop(state: NewsState) -> dict:
    return {}


def search_tech(state: NewsState) -> dict:
    return {ARTICLES_KEY: A}


def search_biz(state: NewsState) -> dict:
    return {ARTICLES_KEY: B}


class TestNewsStateWiring:
    def test_reducer_is_attached_to_article_key(self):
        hints = get_type_hints(NewsState, include_extras=True)
        assert merge_article_hits in hints[ARTICLES_KEY].__metadata__

    def test_compiled_graph_uses_aggregate_channel(self):
        g = StateGraph(NewsState)  # ty: ignore[invalid-argument-type]
        g.add_node("noop", noop)
        g.add_edge(START, "noop")
        assert isinstance(g.compile().channels[ARTICLES_KEY], BinaryOperatorAggregate)

    def test_parallel_writers_are_merged_not_rejected(self):
        g = StateGraph(NewsState)  # ty: ignore[invalid-argument-type]
        g.add_node("search_tech", search_tech)
        g.add_node("search_biz", search_biz)
        g.add_edge(START, "search_tech")
        g.add_edge(START, "search_biz")
        out = g.compile().invoke({"query": "q", ARTICLES_KEY: []})
        assert out[ARTICLES_KEY] == EXPECTED_A_B

    @pytest.mark.parametrize("output_type", [CategoryOutput, SearchOutput, SummaryOutput])
    def test_output_keys_are_state_keys(self, output_type):
        # a node returning a key NewsState doesn't declare is silently dropped (S46)
        missing = set(output_type.__annotations__) - set(NewsState.__annotations__)
        assert not missing, f"{output_type.__name__} writes keys NewsState lacks: {missing}"