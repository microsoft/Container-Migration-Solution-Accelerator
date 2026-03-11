# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest

from libs.mcp_server.mermaid.mcp_mermaid import (
    basic_fix_mermaid,
    basic_validate_mermaid,
    extract_mermaid_blocks_from_markdown,
)


class TestMermaidValidator(unittest.TestCase):
    def test_extract_mermaid_blocks_from_markdown(self):
        md = """
# Doc

```mermaid
graph TD
  A-->B
```

```mermaid
sequenceDiagram
  A->>B: hi
```
"""
        blocks = extract_mermaid_blocks_from_markdown(md)
        self.assertEqual(len(blocks), 2)
        self.assertIn("graph TD", blocks[0])
        self.assertIn("sequenceDiagram", blocks[1])

    def test_basic_validate_mermaid_ok(self):
        v = basic_validate_mermaid("graph TD\nA-->B")
        self.assertTrue(v.valid)

    def test_basic_fix_mermaid_prepends_header_when_missing(self):
        fixed, applied, v = basic_fix_mermaid("A-->B")
        self.assertIn("prepend_graph_td", applied)
        self.assertTrue(fixed.startswith("graph TD"))
        self.assertTrue(v.valid)


if __name__ == "__main__":
    unittest.main()
