"""Negative-control fixtures for the Task 38.6 harness (Harness
Requirement 7). None of this module is imported by production code,
registered as a framework, or reachable from ``app.wiring``. Every
"forbidden" call here is a deliberately unsafe pattern the harness's
tests assert get *detected* -- none of it is ever actually executed
with the real operation live; the fixtures exist to be statically
analyzed and, where noted, to prove a runtime patch intercepts them
before any real connection completes.
"""
