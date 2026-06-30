import os

source_root = os.path.dirname(os.path.abspath(__file__))
if source_root not in os.sys.path:
    os.sys.path.insert(0, source_root)
