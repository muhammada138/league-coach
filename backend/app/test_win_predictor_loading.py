import pytest
from unittest.mock import patch, MagicMock

from app.services.win_predictor import load_or_train_model
from app.services import win_predictor

@patch("app.services.win_predictor.Path")
@patch("app.services.win_predictor.logger")
def test_load_or_train_model_import_error(mock_logger, mock_path):
    mock_path.exists.return_value = True

    import_err = ImportError("mock import error")
    with patch("app.services.win_predictor.joblib.load", side_effect=import_err):
        with patch("app.services.win_predictor.MODEL_PATH", mock_path):
            load_or_train_model()

    mock_logger.warning.assert_called_with("Model load failed (%s) – using linear fallback", import_err)


@patch("app.services.win_predictor.Path")
@patch("app.services.win_predictor.joblib.load")
@patch("app.services.win_predictor.logger")
def test_load_or_train_model_exception(mock_logger, mock_load, mock_path):
    mock_path.exists.return_value = True
    test_exception = Exception("test error")
    mock_load.side_effect = test_exception

    with patch("app.services.win_predictor.MODEL_PATH", mock_path):
        load_or_train_model()

    # The actual code snippet from win_predictor.py shows:
    # except Exception as exc:
    #     logger.warning("Model load failed (%s) – using linear fallback", exc)
    mock_logger.warning.assert_called_with("Model load failed (%s) – using linear fallback", test_exception)


@patch("app.services.win_predictor.Path")
@patch("app.services.win_predictor.joblib.load")
@patch("app.services.win_predictor.logger")
def test_load_or_train_model_success(mock_logger, mock_load, mock_path):
    mock_path.exists.return_value = True
    mock_model = MagicMock()
    mock_load.return_value = mock_model

    # Save the original model and reset it
    original_model = win_predictor._model
    win_predictor._model = None

    try:
        with patch("app.services.win_predictor.MODEL_PATH", mock_path):
            load_or_train_model()

        mock_load.assert_called_once()
        assert win_predictor._model is mock_model
    finally:
        # Restore original model
        win_predictor._model = original_model


@patch("app.services.win_predictor.Path")
@patch("app.services.win_predictor.logger")
def test_load_or_train_model_fallback(mock_logger, mock_path):
    mock_path.exists.return_value = False

    with patch("app.services.win_predictor.MODEL_PATH", mock_path):
        load_or_train_model()

    mock_logger.info.assert_called_with("No saved model – using linear fallback until retrained.")
