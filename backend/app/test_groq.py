import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.groq import get_coaching_feedback, ask_coach_question

@pytest.fixture
def mock_no_api_key(mocker):
    return mocker.patch("app.services.groq.GROQ_API_KEY", None)

@pytest.fixture
def mock_with_api_key(mocker):
    return mocker.patch("app.services.groq.GROQ_API_KEY", "fake-api-key")

@pytest.mark.asyncio
async def test_get_coaching_feedback_no_api_key(mock_no_api_key):
    result = await get_coaching_feedback("system", "user")
    assert result == "No API key configured."

@pytest.mark.asyncio
async def test_ask_coach_question_no_api_key(mock_no_api_key):
    result = await ask_coach_question("system", [], "question")
    assert result == "No API key configured."

@pytest.mark.asyncio
async def test_get_coaching_feedback_success(mock_with_api_key, mocker):
    mock_async_groq = mocker.patch("app.services.groq.AsyncGroq")
    mock_client = mock_async_groq.return_value

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "This is a coaching feedback."
    mock_completion.choices = [mock_choice]

    mock_create = AsyncMock(return_value=mock_completion)
    mock_client.chat.completions.create = mock_create

    system_prompt = "You are a coach"
    user_prompt = "How can I improve?"

    result = await get_coaching_feedback(system_prompt, user_prompt)

    assert result == "This is a coaching feedback."
    mock_async_groq.assert_called_once_with(api_key="fake-api-key")
    mock_create.assert_called_once_with(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

@pytest.mark.asyncio
async def test_ask_coach_question_success(mock_with_api_key, mocker):
    mock_async_groq = mocker.patch("app.services.groq.AsyncGroq")
    mock_client = mock_async_groq.return_value

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "This is the answer."
    mock_completion.choices = [mock_choice]

    mock_create = AsyncMock(return_value=mock_completion)
    mock_client.chat.completions.create = mock_create

    system_prompt = "You are a coach answering questions"
    history = [{"role": "user", "content": "Previous question"}, {"role": "assistant", "content": "Previous answer"}]
    question = "My new question"

    result = await ask_coach_question(system_prompt, history, question)

    assert result == "This is the answer."
    mock_async_groq.assert_called_once_with(api_key="fake-api-key")
    mock_create.assert_called_once_with(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
            {"role": "user", "content": question},
        ],
        max_tokens=300,
    )
