from pathlib import Path
import argparse
import webbrowser
import uvicorn

from .server import create_app


def run():
    parser = argparse.ArgumentParser(prog="imzdesk")
    parser.add_argument("path", default='.', help="Target directory")
    parser.add_argument("-H", "--host", default="127.0.0.1")
    parser.add_argument("-P", "--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    data_root = Path(args.path).resolve()

    if not args.no_browser:
        webbrowser.open(f"http://{args.host}:{args.port}")

    factory = create_app(data_root)

    uvicorn.run(
        factory,
        host=args.host,
        port=args.port,
        factory=True,
    )
