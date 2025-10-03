from abc import ABC, abstractmethod

# -------------------------------
# Base Agent
# -------------------------------
class Agent(ABC):
    def __init__(self, name):
        self.name = name
        self.memory = []

    @abstractmethod
    def process(self, task):
        pass

    def remember(self, note):
        self.memory.append(note)