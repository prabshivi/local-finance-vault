# Wrapper entrypoint to redirect to src/app.py
import runpy
import sys
import os

# Add src to python path to support absolute imports within src
src_dir = os.path.join(os.path.dirname(__file__), 'src')
sys.path.insert(0, src_dir)

if __name__ == "__main__":
    runpy.run_path(os.path.join(src_dir, 'app.py'), run_name="__main__")
