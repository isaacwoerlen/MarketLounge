import pytest
from unittest.mock import patch, Mock
import json
from utils_core.env import get_env_variable, load_env_config, is_env_valid
from utils_core.errors import ValidationError

@patch("utils_core.env.Config")
def test_get_env_variable_str(mock_config):
    """Test get_env_variable with string cast."""
    mock_config.return_value.__call__.return_value = "value"
    result = get_env_variable("KEY", cast="str")
    assert result == "value"
    mock_config.return_value.__call__.assert_called_with("KEY", default=None)

@patch("utils_core.env.Config")
def test_get_env_variable_int(mock_config):
    """Test get_env_variable with int cast."""
    mock_config.return_value.__call__.return_value = "123"
    result = get_env_variable("KEY", cast="int")
    assert result == 123

@patch("utils_core.env.Config")
def test_get_env_variable_float(mock_config):
    """Test get_env_variable with float cast."""
    mock_config.return_value.__call__.return_value = "123.45"
    result = get_env_variable("KEY", cast="float")
    assert result == 123.45

@patch("utils_core.env.Config")
def test_get_env_variable_bool(mock_config):
    """Test get_env_variable with bool cast."""
    mock_config.return_value.__call__.return_value = "true"
    assert get_env_variable("KEY", cast="bool") is True
    mock_config.return_value.__call__.return_value = "false"
    assert get_env_variable("KEY", cast="bool") is False

@patch("utils_core.env.Config")
def test_get_env_variable_json(mock_config):
    """Test get_env_variable with json cast."""
    mock_config.return_value.__call__.return_value = '{"key": "value"}'
    result = get_env_variable("KEY", cast="json")
    assert result == {"key": "value"}

@patch("utils_core.env.Config")
def test_get_env_variable_missing(mock_config):
    """Test get_env_variable with missing variable and no default."""
    mock_config.return_value.__call__.return_value = None
    with pytest.raises(ValidationError, match="Missing environment variable: KEY"):
        get_env_variable("KEY")

@patch("utils_core.env.Config")
def test_get_env_variable_default(mock_config):
    """Test get_env_variable with default value."""
    mock_config.return_value.__call__.return_value = None
    result = get_env_variable("KEY", default="default")
    assert result == "default"

@patch("utils_core.env.Config")
def test_get_env_variable_invalid_cast(mock_config):
    """Test get_env_variable with invalid cast."""
    mock_config.return_value.__call__.return_value = "invalid"
    with pytest.raises(ValidationError, match="Cannot cast KEY='invalid' to int"):
        get_env_variable("KEY", cast="int")
    with pytest.raises(ValidationError, match="Cannot cast KEY='invalid' to json"):
        get_env_variable("KEY", cast="json")

@patch("utils_core.env.Config")
def test_get_env_variable_lru_cache(mock_config):
    """Test that get_env_variable uses LRU cache."""
    mock_config.return_value.__call__.return_value = "value"
    result1 = get_env_variable("KEY", cast="str")
    result2 = get_env_variable("KEY", cast="str")
    assert result1 == result2 == "value"
    mock_config.return_value.__call__.assert_called_once_with("KEY", default=None)

@patch("utils_core.env.Config")
def test_load_env_config_success(mock_config):
    """Test load_env_config with valid file."""
    mock_config.return_value = Mock()
    load_env_config(".env")
    mock_config.assert_called_with(RepositoryEnv(".env"))

@patch("utils_core.env.Config")
def test_load_env_config_failure(mock_config):
    """Test load_env_config with invalid file."""
    mock_config.side_effect = Exception("File not found")
    with pytest.raises(ValidationError, match="Failed to load .env file .env"):
        load_env_config(".env")

@patch("utils_core.env.Config")
def test_is_env_valid_all_present(mock_config):
    """Test is_env_valid when all required variables are present."""
    mock_config.return_value.__call__.side_effect = lambda key, default: key
    assert is_env_valid(["KEY1", "KEY2"]) is True

@patch("utils_core.env.Config")
def test_is_env_valid_missing(mock_config):
    """Test is_env_valid when some variables are missing."""
    mock_config.return_value.__call__.side_effect = lambda key, default: None
    with pytest.raises(ValidationError, match="Missing required environment variables: KEY1, KEY2"):
        is_env_valid(["KEY1", "KEY2"])