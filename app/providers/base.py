from abc import ABC, abstractmethod
from app.models.alert import AlertPayload


class BaseNotificationProvider(ABC):
    """Abstract interface for all outbound alert notification dispatchers."""

    @abstractmethod
    async def send(self, alert: AlertPayload) -> bool:
        """Dispatch the alert to the target notification channel.

        :param alert: Normalized AlertPayload
        :return: True if delivery succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Gracefully release network connections and client sessions."""
        pass
