"""Tiny self-contained module used by the taskforge self-test fixture."""


def max_depth(s: str) -> int:
    """Maximum depth of nested parentheses in s."""
    depth = 0
    best = 0
    for ch in s:
        if ch == "(":
            depth += 1
            if depth > best:
                best = depth
        elif ch == ")":
            depth -= 1
    return best
