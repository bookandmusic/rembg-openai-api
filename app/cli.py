from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rembg.sessions import sessions

from .download_proxy import github_proxy_prefix, patch_pooch_retrieve
from .models_registry import is_model_available, supported_model_ids


def resolve_session(model_id: str):
    return sessions.get(model_id)


def list_models(models_dir: str | Path) -> int:
    root = Path(models_dir)
    ids = supported_model_ids()
    width = max(len(m) for m in ids) + 2
    for model_id in ids:
        status = "installed" if is_model_available(model_id, root) else "missing"
        print(f"{model_id:<{width}} {status}")
    return 0


def download_model(model_id: str, models_dir: str | Path) -> None:
    if model_id not in supported_model_ids():
        print(f"unknown model: {model_id}", file=sys.stderr)
        print(f"supported: {', '.join(supported_model_ids())}", file=sys.stderr)
        raise SystemExit(1)
    cls = resolve_session(model_id)
    if cls is None:
        print(f"model {model_id} has no rembg session", file=sys.stderr)
        raise SystemExit(1)
    root = Path(models_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["U2NET_HOME"] = str(root)
    proxy = github_proxy_prefix()
    if proxy:
        print(f"Using GITHUB_PROXY: {proxy}")
    print(f"Downloading {model_id} -> {root}")
    unpatch = patch_pooch_retrieve()
    try:
        cls.download_models()
    finally:
        unpatch()


def _add_dir(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--dir",
        default=os.environ.get("U2NET_HOME", "/models"),
        help="models directory (default: $U2NET_HOME or /models)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="models",
        description="List and download rembg models for rembg-openai-api",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list supported models and install status")
    _add_dir(p_list)

    p_pull = sub.add_parser("pull", help="download model(s)")
    _add_dir(p_pull)
    p_pull.add_argument("models", nargs="*", help="model ids")
    p_pull.add_argument("--all", action="store_true", help="download all models")

    args = parser.parse_args(argv)
    models_dir = args.dir

    if args.cmd == "list":
        return list_models(models_dir)

    if args.cmd == "pull":
        if args.all:
            targets = supported_model_ids()
        else:
            targets = list(args.models)
        if not targets:
            print("usage: models pull <model> [...] | models pull --all", file=sys.stderr)
            return 2
        for m in targets:
            download_model(m, models_dir)
        print("Done.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
