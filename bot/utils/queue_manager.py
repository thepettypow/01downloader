import asyncio
from bot.config.settings import config

class DownloadQueue:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(config.max_concurrent_downloads)
        self.waiting = 0

    async def acquire(self):
        self.waiting += 1
        return self.waiting

    async def wait_and_acquire(self):
        await self.semaphore.acquire()
        self.waiting -= 1

    def release(self):
        self.semaphore.release()

queue_manager = DownloadQueue()
