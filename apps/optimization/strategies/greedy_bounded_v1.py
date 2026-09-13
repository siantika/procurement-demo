"""Public strategy entry point for optimizer version greedy-bounded-v1."""

from apps.optimization.engine import optimize


def run(items, **kwargs):
    return optimize(items, **kwargs)
