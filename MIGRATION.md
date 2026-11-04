# Go rewrite

The native application uses Bubble Tea v2, Bubbles v2 and Lip Gloss v2.
Settings remain compatible with the Python application's user settings file.

Implementation milestones:
1. Native LCU transport, process discovery and settings compatibility.
2. Gameflow automation with position-aware picks, bans and requeue.
3. Responsive terminal interface, searchable champion picker and settings.
4. Tests, Windows executable and build documentation.

The Python implementation remains available during migration for comparison.

Implemented: native process discovery and authenticated LCU requests, shared
settings, ready checks, primary/secondary pools and backups, autofill pause,
independent pick/ban controls, configurable action delays from settings, swaps,
honor skipping, requeue, searchable champion wizard, recent selections, native
release updates, Windows CI build and automated tests.

Live matchmaking validation requires an active League Client and has not been
performed as part of the offline test suite. Existing spell fields are preserved;
the Python application did not automate spell selection either.
