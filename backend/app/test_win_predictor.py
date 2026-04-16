import logging
import pytest
from app.services import win_predictor

def test_load_or_train_model_import_error(mocker, caplog):
    # Mock sys.modules to simulate ImportError when locally importing joblib or sklearn inside load_or_train_model
    mocker.patch.dict("sys.modules", {"sklearn.ensemble": None})

    with caplog.at_level(logging.ERROR):
        win_predictor.load_or_train_model()

    assert "scikit-learn is not installed." in caplog.text

def test_load_or_train_model_exception(mocker, caplog):
    # Mock joblib.load globally to simulate a generic Exception
    mocker.patch("joblib.load", side_effect=Exception("mocked generic error"))
    mocker.patch("pathlib.Path.exists", return_value=True)

    with caplog.at_level(logging.WARNING):
        win_predictor.load_or_train_model()

    assert "Model load failed (mocked generic error) – using linear fallback" in caplog.text
