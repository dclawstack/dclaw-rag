from app.core.config import Settings, validate_runtime_config


def _settings(**overrides):
    base = {
        "_env_file": None,  # ignore any local .env so the test is deterministic
        "admin_api_key": "real-admin-secret",
        "bootstrap_api_key": None,
        "cors_allow_origins": ["https://app.example.com"],
        "llm_provider": "ollama",  # local provider needs no key
        "jwt_secret": "a-strong-production-jwt-secret-value-1234",
    }
    base.update(overrides)
    return Settings(**base)


def test_valid_production_config_has_no_problems():
    assert validate_runtime_config(_settings()) == []


def test_missing_admin_key_is_flagged():
    problems = validate_runtime_config(_settings(admin_api_key=None))
    assert any("ADMIN_API_KEY" in p for p in problems)


def test_dev_placeholder_key_is_flagged():
    problems = validate_runtime_config(_settings(admin_api_key="sk_admin_dev"))
    assert any("placeholder" in p for p in problems)


def test_wildcard_cors_is_flagged():
    problems = validate_runtime_config(_settings(cors_allow_origins=["*"]))
    assert any("CORS" in p for p in problems)


def test_dev_or_weak_jwt_secret_is_flagged():
    assert any(
        "JWT_SECRET" in p
        for p in validate_runtime_config(
            _settings(jwt_secret="dev-insecure-jwt-secret-change-me")
        )
    )
    assert any("JWT_SECRET" in p for p in validate_runtime_config(_settings(jwt_secret="short")))


def test_missing_provider_key_is_flagged():
    problems = validate_runtime_config(
        _settings(llm_provider="openai", openai_api_key=None)
    )
    assert any("openai" in p.lower() for p in problems)


def test_configured_provider_key_passes():
    assert validate_runtime_config(
        _settings(llm_provider="openai", openai_api_key="sk-real")
    ) == []


# --- local-mode profile ---


def test_local_profile_defaults():
    s = Settings(_env_file=None, app_mode="local", data_dir="/tmp/dclaw-test")
    assert s.rate_limit_per_minute == 0
    assert s.embedding_model == "BAAI/bge-small-en-v1.5"
    assert s.embedding_dim == 384
    assert s.bootstrap_api_key == "sk_local"
    assert str(s.sqlite_path) == "/tmp/dclaw-test/kv.sqlite3"
    assert str(s.qdrant_path) == "/tmp/dclaw-test/qdrant"


def test_local_profile_explicit_values_win():
    s = Settings(
        _env_file=None,
        app_mode="local",
        rate_limit_per_minute=5,
        embedding_model="BAAI/bge-large-en-v1.5",
        bootstrap_api_key="sk_custom",
    )
    assert s.rate_limit_per_minute == 5
    assert s.embedding_model == "BAAI/bge-large-en-v1.5"
    assert s.embedding_dim == 1024
    assert s.bootstrap_api_key == "sk_custom"


def test_server_mode_keeps_existing_defaults():
    s = Settings(_env_file=None)
    assert s.app_mode == "server"
    assert s.rate_limit_per_minute == 60
    assert s.embedding_model == "BAAI/bge-large-en-v1.5"
    assert s.embedding_dim == 1024
