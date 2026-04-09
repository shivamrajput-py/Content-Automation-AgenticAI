from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from ..common.logging import configure_logging
from ..common.settings import CommonSettings
from .graph import build_graph
from .schemas import SocialAutopostInput


def _load_payload(path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LinkedIn/Twitter autopost LangGraph workflow.")
    parser.add_argument("--input", help="Path to a JSON input file.")
    parser.add_argument("--thread-id", default=str(uuid4()))
    args = parser.parse_args()

    configure_logging()
    settings = CommonSettings()
    payload = SocialAutopostInput.model_validate(_load_payload(args.input))
    graph = build_graph(settings)
    result = graph.invoke(
        {"request": payload.model_dump(mode="json")},
        config={"configurable": {"thread_id": args.thread_id}},
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
