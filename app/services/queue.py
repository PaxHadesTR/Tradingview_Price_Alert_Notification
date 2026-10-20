import asyncio
import logging
from typing import List, Optional
from app.models.alert import AlertPayload
from app.providers.base import BaseNotificationProvider
from app.services.rate_limiter import AsyncTokenBucket

logger = logging.getLogger(__name__)


class AlertQueueService:
    """Asynchronous in-memory queue manager with background worker dispatching to notification providers."""

    def __init__(
        self,
        providers: List[BaseNotificationProvider],
        rate_limiter: AsyncTokenBucket,
        max_capacity: int = 500,
    ) -> None:
        self.providers = providers
        self.rate_limiter = rate_limiter
        self.max_capacity = max_capacity
        self.queue: asyncio.Queue[AlertPayload] = asyncio.Queue(maxsize=max_capacity)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._total_processed = 0
        self._total_failed = 0

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Start the background consumer task."""
        if self._worker_task and not self._worker_task.done():
            return
        self._running = True
        try:
            target_loop = loop or asyncio.get_running_loop()
            self._worker_task = target_loop.create_task(self._worker_loop(), name="alert_queue_worker")
            logger.info("AlertQueueService background worker started with capacity %d.", self.max_capacity)
        except RuntimeError:
            logger.debug("No active event loop running when starting queue; worker will attach when loop starts.")

    async def stop(self) -> None:
        """Gracefully stop the background worker and close providers."""
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        for provider in self.providers:
            try:
                await provider.close()
            except Exception as e:
                logger.warning("Error closing provider %s: %s", provider, e)

        logger.info("AlertQueueService stopped. Total processed: %d, failed: %d", self._total_processed, self._total_failed)

    def enqueue(self, alert: AlertPayload) -> bool:
        """Enqueue an alert without blocking. Returns False if queue is full."""
        if self._worker_task is None or self._worker_task.done():
            self.start()
        try:
            self.queue.put_nowait(alert)
            return True
        except asyncio.QueueFull:
            logger.error("Alert queue is full (%d)! Dropping alert for %s", self.max_capacity, alert.ticker)
            self._total_failed += 1
            return False

    async def _worker_loop(self) -> None:
        """Continuous worker that retrieves items, enforces rate limits, and dispatches to providers."""
        while self._running:
            try:
                alert = await self.queue.get()
            except asyncio.CancelledError:
                break

            try:
                # Apply rate limiting
                await self.rate_limiter.acquire()

                # Dispatch concurrently to all configured providers
                tasks = [provider.send(alert) for provider in self.providers]
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception) or r is False:
                            self._total_failed += 1
                        else:
                            self._total_processed += 1
                else:
                    logger.debug("No notification providers registered. Alert dequeued without dispatch.")
                    self._total_processed += 1

            except asyncio.CancelledError:
                self.queue.task_done()
                break
            except Exception as e:
                logger.error("Unexpected error in alert worker loop: %s", e, exc_info=True)
                self._total_failed += 1
            finally:
                self.queue.task_done()

    @property
    def stats(self) -> dict:
        """Return diagnostic health and throughput metrics."""
        return {
            "queue_size": self.queue.qsize(),
            "max_capacity": self.max_capacity,
            "running": self._running,
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
        }
