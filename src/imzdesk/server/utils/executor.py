import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar, cast

from fastapi import Request

logger = logging.getLogger(__name__)

P = ParamSpec('P')
R = TypeVar('R')


def threaded(function: Callable[P, R]) -> Callable[Concatenate[Request, P], Awaitable[R]]:
    """
    Run a synchronous function in the app's worker thread pool.

    The wrapped function receives a FastAPI ``Request`` as an extra first argument. The request is used to access
    ``request.app.state.executor`` and is not passed to the synchronous function.
    """

    @functools.wraps(function)
    async def wrapper(request: Request, *args: P.args, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_running_loop()
        call = functools.partial(function, *args, **kwargs)
        started = time.perf_counter()
        logger.debug(
            'Dispatching worker function=%s positional_args=%d keyword_args=%s',
            function.__qualname__,
            len(args),
            sorted(kwargs),
        )
        try:
            result = await loop.run_in_executor(request.app.state.executor, call)
        except Exception:
            logger.exception(
                'Worker failed function=%s duration_ms=%.2f',
                function.__qualname__,
                (time.perf_counter() - started) * 1000,
            )
            raise
        logger.debug(
            'Worker completed function=%s duration_ms=%.2f',
            function.__qualname__,
            (time.perf_counter() - started) * 1000,
        )
        return result

    return cast(Callable[Concatenate[Request, P], Awaitable[R]], wrapper)
