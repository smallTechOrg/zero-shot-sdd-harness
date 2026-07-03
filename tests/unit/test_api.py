"""API contract tests — no LLM key required (the agent graph is not invoked)."""

_TINY_CSV = b"region,amount\nNorth,100\nSouth,200\nNorth,50\n"


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_small_csv_profiles(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("mini.csv", _TINY_CSV, "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 3
    assert data["column_count"] == 2
    assert data["file_format"] == "csv"
    names = {c["name"] for c in data["profile"]["columns"]}
    assert names == {"region", "amount"}


def test_upload_unsupported_extension_rejected(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "UNSUPPORTED_FILE"


def test_upload_empty_file_rejected(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert r.status_code == 400


def test_list_datasets_after_upload(api_client):
    api_client.post("/datasets", files={"file": ("mini.csv", _TINY_CSV, "text/csv")})
    r = api_client.get("/datasets")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) >= 1
    assert {"id", "name", "row_count", "column_count", "created_at"} <= set(rows[0])


def test_get_dataset_not_found(api_client):
    r = api_client.get("/datasets/nope")
    assert r.status_code == 404


def test_get_run_not_found(api_client):
    r = api_client.get("/runs/nonexistent-id")
    assert r.status_code == 404


def test_run_unknown_dataset_returns_404(api_client):
    r = api_client.post("/runs", json={"dataset_id": "nope", "question": "total?"})
    assert r.status_code == 404


def test_run_blank_question_returns_400(api_client):
    r = api_client.post("/runs", json={"dataset_id": "nope", "question": "   "})
    assert r.status_code == 400


def test_run_missing_body_field_422(api_client):
    r = api_client.post("/runs", json={"dataset_id": "x"})
    assert r.status_code == 422
