import sys
import os

# Add src directory to PYTHONPATH for all test runs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
