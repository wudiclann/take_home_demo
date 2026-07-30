"""Real (no-mock) tests for the retrieval pipeline: BM25, RRF merge, and the
full hybrid-search-then-rerank pipeline, against the ingested sample PDF.
Hits the real OpenAI embeddings API and loads the real cross-encoder model.
"""


def test_bm25_search_finds_keyword_match(sample_document_id):
    from app.core.keyword_search import bm25_search

    results = bm25_search(sample_document_id, "BLEU", top_k=5)
    assert results
    _top_chunk_id, top_score = results[0]
    assert top_score > 0


def test_reciprocal_rank_fusion_merges_by_shared_id():
    # Pure unit test of the merge math -- no API calls, fast and deterministic.
    from app.core.retrieval import reciprocal_rank_fusion

    bm25_ids = ["a", "b", "c"]
    vector_ids = ["b", "c", "d"]
    merged_ids = [chunk_id for chunk_id, _score in reciprocal_rank_fusion(bm25_ids, vector_ids)]

    # "b" and "c" appear in both ranked lists, so RRF should rank them above
    # ids that only appeared in one list.
    assert merged_ids.index("b") < merged_ids.index("a")
    assert merged_ids.index("c") < merged_ids.index("d")
    # RRF is a union, not an intersection -- "d" only appeared in one list but
    # should still be present.
    assert "d" in merged_ids


def test_hybrid_search_returns_descending_scores(sample_document_id):
    from app.core.retrieval import hybrid_search

    results = hybrid_search(sample_document_id, "What is multi-head attention?", top_k=10)
    assert results
    scores = [score for _chunk_id, score in results]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_full_pipeline_returns_relevant_top3(sample_document_id):
    from app.core.retrieval import retrieve

    results = retrieve(
        sample_document_id, "What is multi-head attention?", hybrid_k=20, final_k=3
    )
    assert len(results) == 3

    rerank_scores = [r.rerank_score for r in results]
    assert rerank_scores == sorted(rerank_scores, reverse=True)

    combined_text = " ".join(r.text.lower() for r in results)
    assert "attention" in combined_text
    for r in results:
        assert r.chunk_id
        assert r.start_page is not None and r.end_page is not None


def test_retrieve_out_of_scope_query_scores_below_refusal_threshold(sample_document_id):
    from app.core.rag import REFUSAL_THRESHOLD
    from app.core.retrieval import retrieve

    results = retrieve(
        sample_document_id,
        "Does the paper report any results on ImageNet image classification?",
        hybrid_k=20,
        final_k=3,
    )
    assert results
    assert results[0].rerank_score < REFUSAL_THRESHOLD
