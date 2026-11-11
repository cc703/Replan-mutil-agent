"""Stable named PCG64 substreams."""

import numpy as np

STREAMS = (
    "resources",
    "workflow",
    "attributes",
    "lags",
    "setups",
    "skills",
    "persons",
    "calendars",
    "maintenance",
    "releases",
    "weights",
    "deadlines",
)


def streams(seed: int) -> dict[str, np.random.Generator]:
    """Return named PCG64 generators for a nonnegative integer seed.

    STREAMS defines spawn-key indices. Each call returns fresh mutable RNGs;
    consuming one advances it but does not modify global NumPy random state.
    Invalid seeds are rejected by NumPy; this helper does not check API bounds."""
    return {
        name: np.random.Generator(np.random.PCG64(np.random.SeedSequence(seed, spawn_key=(i,))))
        for i, name in enumerate(STREAMS)
    }
