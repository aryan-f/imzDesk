import asyncio
import logging
import sys

from imzdesk.server.logging import CustomHandler, LogBroker


def log_record(message, args=(), exc_info=None):
    return logging.LogRecord(
        name='imzdesk.server.test',
        level=logging.ERROR if exc_info else logging.DEBUG,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args,
        exc_info=exc_info,
    )


def test_log_serialization_formats_arguments_for_frontend():
    event = CustomHandler.serialize(log_record('Loaded %d spectra from %s', (3, 'sample.imzML')))

    assert event['msg'] == 'Loaded 3 spectra from sample.imzML'
    assert event['name'] == 'imzdesk.server.test'
    assert event['level'] == 'DEBUG'
    assert event['thread'] == 'MainThread'


def test_log_serialization_includes_exception_traceback():
    try:
        raise RuntimeError('render failed')
    except RuntimeError:
        exc_info = sys.exc_info()

    event = CustomHandler.serialize(log_record('Unable to render %s', ('sample.imzML',), exc_info))

    assert event['msg'].startswith('Unable to render sample.imzML\nTraceback (most recent call last):')
    assert 'RuntimeError: render failed' in event['msg']


def test_log_broker_publishes_to_active_subscribers():
    async def exercise():
        broker = LogBroker()
        subscription = broker.subscribe()
        pending = asyncio.create_task(anext(subscription))
        await asyncio.sleep(0)

        event = {'msg': 'ready'}
        broker.publish(event)

        assert await pending == event
        await subscription.aclose()
        assert not broker.queues

    asyncio.run(exercise())
