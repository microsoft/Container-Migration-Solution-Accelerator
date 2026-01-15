# Configuration file for pytest in the blob storage tests directory

import sys
import os
from pathlib import Path

# Add the backend-api src directory to the Python path
test_dir = Path(__file__).parent
backend_src_dir = test_dir / ".." / ".." / ".." / ".." / ".." / "backend-api" / "src"
backend_src_path = str(backend_src_dir.resolve())

if backend_src_path not in sys.path:
    sys.path.insert(0, backend_src_path)

# Set PYTHONPATH environment variable as well
current_pythonpath = os.environ.get('PYTHONPATH', '')
if backend_src_path not in current_pythonpath:
    if current_pythonpath:
        os.environ['PYTHONPATH'] = f"{backend_src_path}{os.pathsep}{current_pythonpath}"
    else:
        os.environ['PYTHONPATH'] = backend_src_path

# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]