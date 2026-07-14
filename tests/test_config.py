from app.config import Settings


def test_defaults():
    s = Settings.from_env({})
    assert s.default_model == "u2netp"
    assert s.u2net_home == "/models"
    assert s.max_sessions == 4
    assert s.max_image_bytes == 25 * 1024 * 1024
    assert s.api_key is None
    assert s.file_ttl_seconds == 3600
    assert s.public_base_url == "http://localhost:8000"
    assert s.max_concurrent == 2
    assert s.max_file_store_items == 64
    assert s.max_file_store_bytes == 256 * 1024 * 1024


def test_from_env_overrides():
    s = Settings.from_env(
        {
            "U2NET_HOME": "/data/models",
            "DEFAULT_MODEL": "u2net",
            "MAX_SESSIONS": "2",
            "MAX_IMAGE_BYTES": "1024",
            "API_KEY": "sk-x",
            "FILE_TTL_SECONDS": "10",
            "PUBLIC_BASE_URL": "https://api.example.com/",
            "MAX_CONCURRENT": "3",
            "MAX_FILE_STORE_ITEMS": "8",
            "MAX_FILE_STORE_BYTES": "1000",
        }
    )
    assert s.u2net_home == "/data/models"
    assert s.default_model == "u2net"
    assert s.max_sessions == 2
    assert s.max_image_bytes == 1024
    assert s.api_key == "sk-x"
    assert s.file_ttl_seconds == 10
    assert s.public_base_url == "https://api.example.com"
    assert s.max_concurrent == 3
    assert s.max_file_store_items == 8
    assert s.max_file_store_bytes == 1000
