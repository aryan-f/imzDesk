import asyncio
import logging


class LogBroker:

    def __init__(self):
        self.queues = set()
        self.running = True

    def publish(self, event):
        for queue in self.queues:
            queue.put_nowait(event)

    async def subscribe(self):
        queue = asyncio.Queue()
        self.queues.add(queue)
        try:
            while self.running:
                yield await queue.get()
        finally:
            self.queues.discard(queue)

    def stop(self):
        self.running = False


class CustomHandler(logging.Handler):

    def __init__(self, loop: asyncio.AbstractEventLoop, level: int | str = 0):
        super().__init__(level)
        self.loop = loop
        self.broker = LogBroker()

    def emit(self, record: logging.LogRecord):
        self.loop.call_soon_threadsafe(self.broker.publish, self.serialize(record))

    @classmethod
    def serialize(cls, record: logging.LogRecord):
        return {
            'name': record.name,
            'level': record.levelname,
            'created': record.created,
            'module': record.module,
            'msg': record.msg,
            'thread': record.threadName,
        }
