"""A cross-file caller of nesting.max_depth — proves a signature-preserving stub keeps the project
importable (report imports nesting at module load) even when the behaviour is gutted."""
from nesting import max_depth


def summary(s):
    return "depth=%d" % max_depth(s)
