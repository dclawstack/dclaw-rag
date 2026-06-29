from app.core.config import Settings, validate_runtime_config


def _settings(**overrides):
    base = {
        "_env_file": None,  # ignore any local .env so the test is deterministic
        "admin_api_key": "real-admin-secret",
        "bootstrap_api_key": None,
        "cors_allow_origins": ["https://app.example.com"],
        "llm_provider": "ollama",  # local provider needs no key
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


def test_missing_provider_key_is_flagged():
    problems = validate_runtime_config(
        _settings(llm_provider="openai", openai_api_key=None)
    )
    assert any("openai" in p.lower() for p in problems)


def test_configured_provider_key_passes():
    assert validate_runtime_config(
        _settings(llm_provider="openai", openai_api_key="sk-real")
    ) == []
