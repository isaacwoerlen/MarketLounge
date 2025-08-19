import os
import pytest
from utils_core.env import get_env_variable, load_env_config, ENV_SCHEMA

def test_get_env_variable_nominal():
    """Teste la récupération d'une variable avec cast."""
    os.environ["TEST_EMBEDDING_DIM"] = "384"
    value = get_env_variable("TEST_EMBEDDING_DIM", cast="int", default=256)
    assert value == 384

def test_get_env_variable_default():
    """Teste la récupération avec défaut."""
    os.environ.pop("MISSING_VAR", None)
    value = get_env_variable("MISSING_VAR", cast="float", default=5.0)
    assert value == 5.0

def test_get_env_variable_schema():
    """Teste le schema avec load_env_config."""
    os.environ["EMBEDDING_DIM"] = "512"
    os.environ["LLM_TIMEOUT"] = "10.0"
    config = load_env_config(ENV_SCHEMA)
    assert config["EMBEDDING_DIM"] == 512
    assert config["LLM_TIMEOUT"] == 10.0

def test_get_env_variable_validation_error():
    """Teste une validation échouée."""
    os.environ["INVALID_DIM"] = "50"
    with pytest.raises(ValueError, match="below minimum"):
        get_env_variable("INVALID_DIM", cast="int", min_value=100)