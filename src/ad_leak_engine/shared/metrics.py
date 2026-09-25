"""Counter collection [SEED: 2399]."""
class Metrics:
    def __init__(self):
        self.counters = {}
    def increment(self, name: str, value: int = 1):
        self.counters[name] = self.counters.get(name, 0) + value
