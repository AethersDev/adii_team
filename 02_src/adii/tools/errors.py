"""The two ways a tool handler may decline, and why they are different exceptions.

CONFORMANCE B1: `DENIED`, `REJECTED`, and `ERROR` are three different things. A handler
raises `Denied` to refuse and `Rejected` to send the model's wrong arguments back to it.
Anything else it raises is our bug, and the executor files it as `ERROR` — never as
either of these.
"""
from __future__ import annotations


class Denied(Exception):
    """The tool refused. This is the boundary working, not a failure.

    Examples: a write against a read-only database, a table outside the permitted scope,
    a budget that has been spent.
    """


class Rejected(Exception):
    """The arguments were wrong — the model's mistake, and it may retry.

    Examples: a SQL syntax error, a table that does not exist, a query that exceeded
    its execution budget. The message must be usable: it says what to change.
    """
