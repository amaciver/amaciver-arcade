"""Shared test fixtures for meow_me tests."""

import pytest

# Sample MeowFacts API responses
SAMPLE_SINGLE_FACT_RESPONSE = {
    "data": ["Cats sleep 70% of their lives."]
}

SAMPLE_MULTI_FACT_RESPONSE = {
    "data": [
        "Cats sleep 70% of their lives.",
        "A group of cats is called a clowder.",
        "Cats have over 20 vocalizations, including the purr.",
    ]
}

SAMPLE_EMPTY_FACT_RESPONSE = {
    "data": []
}

# Sample Slack API responses
SAMPLE_AUTH_TEST_RESPONSE = {
    "ok": True,
    "url": "https://test-workspace.slack.com/",
    "team": "Test Workspace",
    "user": "testuser",
    "team_id": "T12345678",
    "user_id": "U12345678",
}

SAMPLE_AUTH_TEST_FAILURE = {
    "ok": False,
    "error": "invalid_auth",
}

SAMPLE_CHAT_POST_SUCCESS = {
    "ok": True,
    "channel": "D12345678",
    "ts": "1234567890.123456",
    "message": {
        "text": ":cat: *Meow Fact:*\nCats sleep 70% of their lives.",
    },
}

SAMPLE_CHAT_POST_FAILURE = {
    "ok": False,
    "error": "channel_not_found",
}


@pytest.fixture
def single_fact_response():
    return SAMPLE_SINGLE_FACT_RESPONSE


@pytest.fixture
def multi_fact_response():
    return SAMPLE_MULTI_FACT_RESPONSE


@pytest.fixture
def empty_fact_response():
    return SAMPLE_EMPTY_FACT_RESPONSE


@pytest.fixture
def auth_test_response():
    return SAMPLE_AUTH_TEST_RESPONSE


@pytest.fixture
def chat_post_success():
    return SAMPLE_CHAT_POST_SUCCESS
