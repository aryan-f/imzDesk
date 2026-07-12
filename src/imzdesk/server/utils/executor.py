import asyncio
import functools
import logging
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
        logger.debug(f'Spawning worker thread for {function.__qualname__}')
        return await loop.run_in_executor(request.app.state.executor, call)

    return cast(Callable[Concatenate[Request, P], Awaitable[R]], wrapper)
