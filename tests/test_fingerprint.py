from llm_replay_proxy.fingerprint import canonical_json, fingerprint_request


def test_fingerprint_is_stable_across_json_and_query_order() -> None:
    first = fingerprint_request(
        "post",
        "v1/chat/completions",
        "beta=2&alpha=1",
        {"messages": [{"content": "hello", "role": "user"}], "model": "demo"},
    )
    second = fingerprint_request(
        "POST",
        "/v1/chat/completions",
        "alpha=1&beta=2",
        {"model": "demo", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert first.key == second.key
    assert first.path == "/v1/chat/completions"
    assert first.query == (("alpha", "1"), ("beta", "2"))


def test_fingerprint_changes_when_semantic_input_changes() -> None:
    first = fingerprint_request("POST", "/v1/responses", "", {"temperature": 0})
    second = fingerprint_request("POST", "/v1/responses", "", {"temperature": 1})

    assert first.key != second.key


def test_canonical_json_rejects_non_finite_numbers() -> None:
    try:
        canonical_json({"score": float("nan")})
    except ValueError as exc:
        assert "Out of range" in str(exc)
    else:
        raise AssertionError("non-finite numbers must not be fingerprinted")
