from __future__ import annotations

from unittest.mock import patch

from app.download_proxy import (
    github_proxy_prefix,
    patch_pooch_retrieve,
    rewrite_download_url,
)


def test_no_proxy():
    assert rewrite_download_url(
        "https://github.com/a/b/x.onnx", env={}
    ) == "https://github.com/a/b/x.onnx"


def test_gh_proxy_com():
    env = {"GITHUB_PROXY": "https://gh-proxy.com/"}
    assert (
        rewrite_download_url(
            "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
            env=env,
        )
        == "https://gh-proxy.com/https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
    )


def test_proxy_without_trailing_slash():
    env = {"GITHUB_PROXY": "https://gh-proxy.com"}
    assert github_proxy_prefix(env) == "https://gh-proxy.com/"
    url = rewrite_download_url("https://github.com/o/r/f.onnx", env=env)
    assert url == "https://gh-proxy.com/https://github.com/o/r/f.onnx"


def test_non_github_unchanged():
    env = {"GITHUB_PROXY": "https://gh-proxy.com/"}
    assert (
        rewrite_download_url("https://example.com/a.onnx", env=env)
        == "https://example.com/a.onnx"
    )


def test_already_proxied():
    env = {"GITHUB_PROXY": "https://gh-proxy.com/"}
    url = "https://gh-proxy.com/https://github.com/a/b.onnx"
    assert rewrite_download_url(url, env=env) == url


def test_releases_proxy_alias():
    env = {"GITHUB_RELEASES_PROXY": "https://mirror.example/"}
    assert rewrite_download_url("https://github.com/a/b", env=env).startswith(
        "https://mirror.example/"
    )


def test_patch_pooch_retrieve():
    import pooch

    seen: list[str] = []
    original = pooch.retrieve

    def fake(url, *a, **k):
        seen.append(url)
        return "/tmp/x"

    pooch.retrieve = fake  # type: ignore[assignment]
    try:
        with patch.dict("os.environ", {"GITHUB_PROXY": "https://gh-proxy.com/"}, clear=False):
            # re-apply patch on top of fake by re-importing wrap logic
            unpatch = patch_pooch_retrieve()
            try:
                pooch.retrieve(
                    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
                    None,
                )
            finally:
                unpatch()
        assert seen == [
            "https://gh-proxy.com/https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
        ]
    finally:
        pooch.retrieve = original  # type: ignore[assignment]
