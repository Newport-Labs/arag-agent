from abc import ABC, abstractmethod


class BaseAgent(ABC):
    @abstractmethod
    def _message(self):
        pass

    @abstractmethod
    def perform_action(self):
        pass
