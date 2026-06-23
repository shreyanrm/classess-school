"""Classess Identity service — Ring 0 secure core.

The ONLY place the opaque canonical_uuid maps to a person (the PII vault).
PII lives here and nowhere else. Everything that leaves this boundary carries
only the opaque canonical_uuid and non-identifying authorization inputs.
"""
