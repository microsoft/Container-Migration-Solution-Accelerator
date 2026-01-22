# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastmcp>=2.12.5",
#   "pytz>=2024.1",
# ]
# ///

import httpx

print("httpx file:", getattr(httpx, "__file__", None))
print("httpx version:", getattr(httpx, "__version__", None))
print("has TransportError:", hasattr(httpx, "TransportError"))
print("dir contains TransportError:", "TransportError" in dir(httpx))
