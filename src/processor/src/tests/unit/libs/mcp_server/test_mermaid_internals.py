# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Coverage for mermaid validation/fix helpers + MCP tool wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from libs.mcp_server.mermaid import mcp_mermaid as mod
from libs.mcp_server.mermaid.mcp_mermaid import (
    _balance_check,
    _detect_diagram_type,
    _first_nonempty_line,
    _mermaid_render_check,
    _normalize_text,
    _strip_fences_if_present,
    basic_fix_mermaid,
    basic_validate_mermaid,
    extract_mermaid_blocks_from_markdown,
)


# -----------------------------------------------------------------------------
# _normalize_text
# -----------------------------------------------------------------------------


class TestNormalizeText:
    def test_none_input(self):
        out, fixes = _normalize_text(None)
        assert out == ""
        assert "input_was_none" in fixes

    def test_normalize_crlf(self):
        out, fixes = _normalize_text("a\r\nb\rc")
        assert out == "a\nb\nc"
        assert "normalize_newlines" in fixes

    def test_replace_smart_quotes(self):
        out, fixes = _normalize_text("\u201chello\u201d")
        assert out == '"hello"'
        assert "replace_smart_quotes" in fixes

    def test_strip_outer_newlines(self):
        out, fixes = _normalize_text("\n\nfoo\n")
        assert "strip_outer_newlines" in fixes

    def test_passthrough(self):
        out, fixes = _normalize_text("plain")
        assert out == "plain"
        assert fixes == []


# -----------------------------------------------------------------------------
# extract_mermaid_blocks_from_markdown
# -----------------------------------------------------------------------------


class TestExtractMermaidBlocks:
    def test_empty_returns_empty(self):
        assert extract_mermaid_blocks_from_markdown("") == []

    def test_extracts_multiple_blocks(self):
        md = """```mermaid
graph TD
A-->B
```
```mermaid
sequenceDiagram
A->>B: x
```"""
        blocks = extract_mermaid_blocks_from_markdown(md)
        assert len(blocks) == 2


# -----------------------------------------------------------------------------
# _strip_fences_if_present
# -----------------------------------------------------------------------------


class TestStripFences:
    def test_empty(self):
        out, fixes = _strip_fences_if_present("")
        assert out == ""
        assert fixes == []

    def test_no_fences(self):
        out, fixes = _strip_fences_if_present("plain")
        assert out == "plain"
        assert fixes == []

    def test_strips_full_fence_block(self):
        out, fixes = _strip_fences_if_present("```mermaid\ngraph TD\nA-->B\n```")
        assert "graph TD" in out
        assert "strip_code_fences" in fixes

    def test_unmatched_fence_returned_unchanged(self):
        out, fixes = _strip_fences_if_present("```mermaid\nno close")
        assert "```" in out
        assert fixes == []


# -----------------------------------------------------------------------------
# _first_nonempty_line / _detect_diagram_type
# -----------------------------------------------------------------------------


class TestDetectDiagramType:
    def test_first_nonempty_line_none(self):
        idx, line = _first_nonempty_line(["", "  ", "\t"])
        assert idx is None
        assert line is None

    def test_first_nonempty_line(self):
        idx, line = _first_nonempty_line(["", " hi ", "next"])
        assert idx == 1
        assert line.strip() == "hi"

    def test_detect_known_prefix(self):
        assert _detect_diagram_type("graph TD\nA-->B") == "graph"

    def test_detect_after_init_directive(self):
        code = "%%{init: {'theme':'dark'}}%%\nflowchart LR\nA-->B"
        assert _detect_diagram_type(code) == "flowchart"

    def test_detect_unknown(self):
        assert _detect_diagram_type("randomtext") is None

    def test_detect_empty(self):
        assert _detect_diagram_type("") is None


# -----------------------------------------------------------------------------
# _balance_check
# -----------------------------------------------------------------------------


class TestBalanceCheck:
    def test_balanced(self):
        assert _balance_check("(a) [b] {c}") == []

    def test_missing_closer(self):
        out = _balance_check("(unclosed")
        assert any("missing closers" in e for e in out)

    def test_unexpected_closer(self):
        out = _balance_check(")")
        assert any("unexpected" in e for e in out)

    def test_unbalanced_quotes(self):
        out = _balance_check('"open quote')
        assert "unbalanced_quotes" in out

    def test_quotes_ignore_brackets(self):
        # Brackets inside quotes don't count
        assert _balance_check('"(([[{{"') == []

    def test_backtick_quotes(self):
        assert _balance_check("`(unbalanced inside ticks`") == []

    def test_escape_handled(self):
        assert _balance_check('\\"a') == []

    def test_single_quote_state(self):
        assert _balance_check("'(unbalanced'") == []


# -----------------------------------------------------------------------------
# basic_validate_mermaid
# -----------------------------------------------------------------------------


class TestBasicValidate:
    def test_empty_diagram(self):
        v = basic_validate_mermaid("")
        assert v.valid is False
        assert "empty_diagram" in v.errors

    def test_missing_header(self):
        v = basic_validate_mermaid("just text")
        assert v.valid is False

    def test_normalization_warning(self):
        v = basic_validate_mermaid("```mermaid\ngraph TD\nA-->B\n```")
        assert "normalized_input" in v.warnings

    def test_valid_diagram(self):
        v = basic_validate_mermaid("graph TD\nA-->B")
        assert v.valid is True
        assert v.diagram_type == "graph"


# -----------------------------------------------------------------------------
# basic_fix_mermaid
# -----------------------------------------------------------------------------


class TestBasicFix:
    def test_removes_markdown_bullets(self):
        fixed, applied, v = basic_fix_mermaid("- A-->B")
        assert "remove_markdown_bullets" in applied

    def test_normalizes_subgraph_label(self):
        fixed, applied, v = basic_fix_mermaid('graph TD\nsubgraph S1["My Group"]\nend')
        assert "normalize_subgraph_labels" in applied
        assert 'subgraph "My Group"' in fixed

    def test_normalizes_subgraph_label_single_quotes(self):
        fixed, applied, v = basic_fix_mermaid("graph TD\nsubgraph S1['Label']\nend")
        assert "normalize_subgraph_labels" in applied

    def test_appends_missing_brackets(self):
        fixed, applied, v = basic_fix_mermaid("graph TD\nA[unclosed")
        assert "append_missing_bracket_closers" in applied

    def test_prepends_graph_when_missing_header(self):
        fixed, applied, v = basic_fix_mermaid("A-->B")
        assert "prepend_graph_td" in applied
        assert fixed.startswith("graph TD")


# -----------------------------------------------------------------------------
# _mermaid_render_check
# -----------------------------------------------------------------------------


class TestMermaidRenderCheck:
    def test_node_not_found_returns_true(self):
        with patch("shutil.which", return_value=None):
            ok, err = _mermaid_render_check("graph TD\nA-->B")
            assert ok is True
            assert err == ""

    def test_subprocess_timeout_returns_true(self):
        import subprocess
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is True

    def test_subprocess_os_error_returns_true(self):
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", side_effect=OSError("boom")):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is True

    def test_valid_response_from_node(self):
        result = MagicMock(returncode=0, stdout='{"valid": true}', stderr="")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is True

    def test_invalid_response_with_error(self):
        result = MagicMock(returncode=0, stdout='{"valid": false, "error": "bad syntax"}', stderr="")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is False
            assert "bad syntax" in err

    def test_skipped_response(self):
        result = MagicMock(returncode=0, stdout='{"valid": true, "skipped": true}', stderr="")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is True

    def test_non_zero_with_error_in_stderr(self):
        result = MagicMock(returncode=1, stdout="", stderr="Error: parse failure\nmore")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is False
            assert "Error" in err

    def test_non_zero_no_error_lines(self):
        result = MagicMock(returncode=1, stdout="", stderr="warning: deprecated\n")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            # stderr without 'Error'/'error' falls through to ok=True
            assert ok is True

    def test_non_json_stdout_falls_through(self):
        result = MagicMock(returncode=0, stdout="not json", stderr="")
        with patch("shutil.which", return_value="/usr/bin/node"), \
             patch("subprocess.run", return_value=result):
            ok, err = _mermaid_render_check("graph TD")
            assert ok is True


# -----------------------------------------------------------------------------
# MCP tool wrappers — call them through their underlying functions
# -----------------------------------------------------------------------------


def _call_tool(tool):
    """fastmcp.@mcp.tool() wraps callables; the underlying fn is .fn."""
    if callable(tool):
        return tool
    fn = getattr(tool, "fn", None)
    if fn is not None:
        return fn
    raise AssertionError(f"Cannot invoke tool {tool!r}")


class TestMcpToolWrappers:
    def test_validate_mermaid_calls_render_when_valid(self):
        with patch.object(mod, "_mermaid_render_check", return_value=(True, "")):
            out = _call_tool(mod.validate_mermaid)("graph TD\nA-->B")
            assert out["valid"] is True

    def test_validate_mermaid_marks_invalid_on_render_failure(self):
        with patch.object(mod, "_mermaid_render_check", return_value=(False, "syntax")):
            out = _call_tool(mod.validate_mermaid)("graph TD\nA-->B")
            assert out["valid"] is False
            assert any("mermaid_render_error" in e for e in out["errors"])

    def test_validate_mermaid_skips_render_when_already_invalid(self):
        with patch.object(mod, "_mermaid_render_check") as render:
            out = _call_tool(mod.validate_mermaid)("")  # empty → invalid
            render.assert_not_called()
            assert out["valid"] is False

    def test_fix_mermaid_calls_render_when_valid(self):
        with patch.object(mod, "_mermaid_render_check", return_value=(True, "")):
            out = _call_tool(mod.fix_mermaid)("A-->B")
            assert out["validation"]["valid"] is True

    def test_fix_mermaid_render_failure_marks_invalid(self):
        with patch.object(mod, "_mermaid_render_check", return_value=(False, "x")):
            out = _call_tool(mod.fix_mermaid)("A-->B")
            assert out["validation"]["valid"] is False

    def test_validate_in_markdown(self):
        md = """```mermaid
graph TD
A-->B
```"""
        with patch.object(mod, "_mermaid_render_check", return_value=(True, "")):
            out = _call_tool(mod.validate_mermaid_in_markdown)(md)
        assert out["blocks_found"] == 1
        assert out["all_valid"] is True

    def test_validate_in_markdown_no_blocks(self):
        out = _call_tool(mod.validate_mermaid_in_markdown)("plain text")
        assert out["blocks_found"] == 0
        assert out["all_valid"] is True

    def test_fix_in_markdown_replaces_blocks(self):
        md = """text\n```mermaid\nA-->B\n```\nmore"""
        with patch.object(mod, "_mermaid_render_check", return_value=(True, "")):
            out = _call_tool(mod.fix_mermaid_in_markdown)(md)
        assert out["blocks_found"] == 1
        assert "graph TD" in out["updated_markdown"]
        assert len(out["per_block_fixes"]) == 1
