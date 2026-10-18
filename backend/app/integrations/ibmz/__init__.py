"""IBM Z integration boundary.

A single adapter interface isolates IBM Z from the rest of the platform. The app
stays fully functional whether the adapter is real, simulated, or unavailable.
Implemented / simulated / future functionality is kept explicitly distinct.
"""
