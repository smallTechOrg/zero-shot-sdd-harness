import pytest
from pydantic import ValidationError
from data_analyst.domain.session import SessionCreate, SessionListItem
from data_analyst.domain.query import QueryRequest, QueryResponse


def test_session_create_default():
    s = SessionCreate()
    assert s.title == "New Session"


def test_session_create_custom():
    s = SessionCreate(title="My Session")
    assert s.title == "My Session"


def test_session_create_title_max_length():
    with pytest.raises(ValidationError):
        SessionCreate(title="x" * 201)


def test_query_request_required():
    with pytest.raises(ValidationError):
        QueryRequest()


def test_query_request_min_length():
    with pytest.raises(ValidationError):
        QueryRequest(question="")


def test_query_request_max_length():
    with pytest.raises(ValidationError):
        QueryRequest(question="x" * 4001)


def test_query_request_valid():
    q = QueryRequest(question="how many rows?")
    assert q.question == "how many rows?"
