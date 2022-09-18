from dataclasses import dataclass


@dataclass
class DataLoggerMeasurement:
    nad: int
    variable: str
    value: str

    def __str__(self):
        return f"c{self.nad}.{self.variable}={self.value}"
