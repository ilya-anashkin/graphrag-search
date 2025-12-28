from hybrid_graphrag_search import eval as eval_mod


def test_metrics_nonzero():
    relevant = ["a", "b"]
    retrieved = ["a", "c", "d"]
    assert eval_mod.recall_at_k(relevant, retrieved, 3) == 0.5
    assert eval_mod.mrr_at_k(relevant, retrieved, 3) == 1.0
    assert eval_mod.ndcg_at_k(relevant, retrieved, 3) > 0
