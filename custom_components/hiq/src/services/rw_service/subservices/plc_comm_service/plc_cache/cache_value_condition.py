from enum import Enum


class CacheValueCondition(Enum):
    FRESH = 0
    STINKY = 1
    STALE = 2

    def __gt__(self, other):
        return self.value > other.value

    def __lt__(self, other):
        return self.value < other.value

    def __ge__(self, other):
        return self == other or self > other

    def __le__(self, other):
        return self == other or self < other
