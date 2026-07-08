"""Route imports through the bpy stubs so pure-logic modules import cleanly."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stubs"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
