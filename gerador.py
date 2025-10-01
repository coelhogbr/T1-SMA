class LinearCongruentialGenerator:
    def __init__(self, seed=1, a=1664525, c=1013904223, m=2**32):
        self.state = seed
        self.a = a
        self.c = c
        self.m = m

    def next_random(self) -> float:
        #intervalo [0,1)
        self.state = (self.a * self.state + self.c) % self.m
        return self.state / self.m