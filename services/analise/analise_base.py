from abc import ABC, abstractmethod


class AnaliseBase(ABC):
    def __init__(self, cidade, crs):
        self.cidade = cidade
        self.crs = crs

    @abstractmethod
    def executar(self):
        pass