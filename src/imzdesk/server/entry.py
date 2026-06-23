import argparse
import os
import pathlib

import uvicorn


def run_server():
    parser = argparse.ArgumentParser(prog='imzdesk')
    parser.add_argument('workspace', type=pathlib.Path, help='workspace dirpath')
    parser.add_argument('--host', default='127.0.0.1', help='server host (default: %(default)s)')
    parser.add_argument('--port', type=int, default=8000, help='server port (default: %(default)s)')
    parser.add_argument('--workers', type=int, default=None, help='number of workers (default: %(default)s)')
    parser.add_argument('--loglevel', default='info', help='log level (default: %(default)s)')
    parser.add_argument('--access-log', action='store_true', help='enable access log (default: %(default)s)')
    parser.add_argument('--reload', action='store_true', help='enable auto-reload (development only)')
    args = parser.parse_args()

    # Inject app settings into environment for `pydantic-settings`
    os.environ['WORKSPACE'] = str(args.workspace.resolve())
    if args.workers is not None:
        os.environ['NUM_WORKERS'] = str(args.workers)

    uvicorn.run(
        'imzdesk.server.app:create_app',
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.loglevel,
        access_log=args.access_log,
    )
