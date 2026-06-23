"""Classess Gateway — THE WALL (Ring 0 secure core).

INVARIANT 3: every service call passes here. The gateway verifies the identity
token, enforces RBAC + ABAC (deny by default), validates the request, writes an
immutable audit record, then routes to the target capability. No capability is
reachable except through this wall.

INVARIANT 11: Track 1 (external LLM routing) and Track 2 (proprietary / edge
models) are configured in two separate sections. The Track 2 slot exists from
line one and is filled later — no re-architecture.
"""
