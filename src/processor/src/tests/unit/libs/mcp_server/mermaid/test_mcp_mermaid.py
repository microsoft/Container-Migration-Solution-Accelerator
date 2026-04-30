# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Unit tests for `libs.mcp_server.mermaid.mcp_mermaid`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from libs.mcp_server.mermaid import mcp_mermaid as mm


# ----- _normalize_text -----

def test_normalize_text_none_returns_empty_with_marker():
    out, fixes = mm._normalize_text(None)  # type: ignore[arg-type]
    assert out == ""
    assert "input_was_none" in fixes


def test_normalize_text_converts_crlf_smart_quotes_and_strips():
    raw = "\n\u201chello\u201d \u2018x\u2019\r\n"
    out, fixes = mm._normalize_text(raw)
    assert '"hello"' in out
    assert "'x'" in out
    assert "normalize_newlines" in fixes
    assert "replace_smart_quotes" in fixes
    assert "strip_outer_newlines" in fixes


def test_normalize_text_no_changes_returns_no_fixes():
    out, fixes = mm._normalize_text("graph TD\nA-->B")
    assert out == "graph TD\nA-->B"
    assert fixes == []


# ----- extract_mermaid_blocks_from_markdown -----

def test_extract_mermaid_blocks_returns_empty_for_falsy_input():
    assert mm.extract_mermaid_blocks_from_markdown("") == []


def test_extract_mermaid_blocks_finds_multiple_blocks_case_insensitive():
    md = (
        "intro\n"
        "```mermaid\ngraph TD\nA-->B\n```\n"
        "middle\n"
        "```Mermaid\nflowchart LR\nC-->D\n```\nend"
    )
    blocks = mm.extract_mermaid_blocks_from_markdown(md)
    assert len(blocks) == 2
    assert "graph TD" in blocks[0]
    assert "flowchart LR" in blocks[1]


# ----- _strip_fences_if_present -----

def test_strip_fences_if_present_strips_mermaid_fences():
    raw = "```mermaid\ngraph TD\nA-->B\n```"
    out, fixes = mm._strip_fences_if_present(raw)
    assert out == "graph TD\nA-->B"
    assert "strip_code_fences" in fixes


def test_strip_fences_if_present_returns_input_when_no_fences():
    raw = "graph TD\nA-->B"
    out, fixes = mm._strip_fences_if_present(raw)
    assert out == raw
    assert fixes == []


def test_strip_fences_if_present_handles_empty_string():
    out, fixes = mm._strip_fences_if_present("")
    assert out == ""
    assert fixes == []


# ----- _detect_diagram_type -----

def test_detect_diagram_type_returns_known_prefix():
    assert mm._detect_diagram_type("graph TD\nA-->B") == "graph"
    assert mm._detect_diagram_type("flowchart LR\nA-->B") == "flowchart"
    assert mm._detect_diagram_type("sequenceDiagram\nA->>B: hi") == "sequenceDiagram"


def test_detect_diagram_type_skips_init_directives():
    code = "%%{init: {'theme': 'dark'}}%%\ngraph TD\nA-->B"
    assert mm._detect_diagram_type(code) == "graph"


def test_detect_diagram_type_returns_none_for_blank():
    assert mm._detect_diagram_type("\n\n   \n") is None


def test_detect_diagram_type_returns_none_for_unknown_prefix():
    assert mm._detect_diagram_type("unknownDiagram\nfoo") is None


# ----- _balance_check -----

def test_balance_check_balanced_returns_empty_list():
    assert mm._balance_check("(a)[b]{c}") == []


def test_balance_check_unbalanced_unexpected_closer():
    errors = mm._balance_check("(a)]")
    assert any("unexpected" in e for e in errors)


def test_balance_check_missing_closers():
    errors = mm._balance_check("(a[")
    assert any("missing closers" in e for e in errors)


def test_balance_check_unbalanced_quotes():
    errors = mm._balance_check('"unterminated')
    assert errors == ["unbalanced_quotes"]


def test_balance_check_ignores_inside_quotes_and_escapes():
    assert mm._balance_check('"(unbalanced"\\)') == []


# ----- basic_validate_mermaid -----

def test_basic_validate_mermaid_empty_returns_invalid():
    v = mm.basic_validate_mermaid("")
    assert v.valid is False
    assert "empty_diagram" in v.errors


def test_basic_validate_mermaid_valid_diagram():
    v = mm.basic_validate_mermaid("graph TD\nA-->B")
    assert v.valid is True
    assert v.diagram_type == "graph"
    assert v.errors == []


def test_basic_validate_mermaid_missing_header_invalid():
    v = mm.basic_validate_mermaid("foo --> bar")
    assert v.valid is False
    assert any("missing_diagram_header" in e for e in v.errors)


def test_basic_validate_mermaid_warns_on_normalization():
    raw = "```mermaid\ngraph TD\nA-->B\n```"
    v = mm.basic_validate_mermaid(raw)
    assert "normalized_input" in v.warnings


# ----- basic_fix_mermaid -----

def test_basic_fix_mermaid_removes_markdown_bullets():
    code = "graph TD\n- A-->B\n* B-->C"
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert "remove_markdown_bullets" in applied
    assert "- " not in fixed
    assert "* " not in fixed
    assert v.valid is True


def test_basic_fix_mermaid_normalizes_subgraph_labels():
    code = 'graph TD\nsubgraph S1["Cluster"]\nend'
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert "normalize_subgraph_labels" in applied
    assert 'subgraph "Cluster"' in fixed


def test_basic_fix_mermaid_normalizes_subgraph_labels_with_single_quotes():
    code = "graph TD\nsubgraph S1['Cluster']\nend"
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert 'subgraph "Cluster"' in fixed


def test_basic_fix_mermaid_prepends_graph_when_header_missing_with_arrows():
    code = "A --> B\nB --> C"
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert fixed.startswith("graph TD")
    assert "prepend_graph_td" in applied
    assert v.valid is True


def test_basic_fix_mermaid_appends_missing_bracket_closers():
    code = "graph TD\nA[B"
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert "append_missing_bracket_closers" in applied
    assert fixed.endswith("]")


def test_basic_fix_mermaid_handles_empty():
    fixed, applied, v = mm.basic_fix_mermaid("")
    assert fixed == ""
    assert v.valid is False


def test_basic_fix_mermaid_strips_fences_and_records_fix():
    code = "```mermaid\ngraph TD\nA-->B\n```"
    fixed, applied, v = mm.basic_fix_mermaid(code)
    assert "strip_code_fences" in applied
    assert "graph TD" in fixed
    assert v.valid is True


# ----- _mermaid_render_check -----

def test_mermaid_render_check_no_node_returns_true():
    with patch.object(mm.shutil, "which", return_value=None):
        ok, err = mm._mermaid_render_check("graph TD\nA-->B")
    assert ok is True
    assert err == ""


def test_mermaid_render_check_subprocess_returns_valid():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=0, stdout='{"valid": true}', stderr=""
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("graph TD\nA-->B")
    assert ok is True
    assert err == ""


def test_mermaid_render_check_subprocess_returns_invalid():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=0,
        stdout='{"valid": false, "error": "syntax bad"}',
        stderr="",
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("graph TD\nA-->B")
    assert ok is False
    assert "syntax bad" in err


def test_mermaid_render_check_subprocess_skipped():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=0,
        stdout='{"valid": true, "skipped": true}',
        stderr="",
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("graph TD")
    assert ok is True


def test_mermaid_render_check_stderr_error_returns_false():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=1, stdout="", stderr="SyntaxError: foo"
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("bad code")
    assert ok is False
    assert "SyntaxError" in err


def test_mermaid_render_check_stderr_no_error_returns_true():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=1, stdout="", stderr="just a warning"
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("code")
    assert ok is True


def test_mermaid_render_check_invalid_json_stdout_falls_back_true():
    fake_run = MagicMock(return_value=MagicMock(
        returncode=0, stdout="not-json", stderr=""
    ))
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", fake_run),
    ):
        ok, err = mm._mermaid_render_check("code")
    assert ok is True


def test_mermaid_render_check_timeout_returns_true():
    def _raise(*a, **kw):
        raise mm.subprocess.TimeoutExpired(cmd="node", timeout=1)

    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", side_effect=_raise),
    ):
        ok, err = mm._mermaid_render_check("code")
    assert ok is True


def test_mermaid_render_check_oserror_returns_true():
    with (
        patch.object(mm.shutil, "which", return_value="/usr/bin/node"),
        patch.object(mm.subprocess, "run", side_effect=OSError("no")),
    ):
        ok, err = mm._mermaid_render_check("code")
    assert ok is True


# ----- MCP tool wrappers -----

def _call_tool(tool_obj, *args, **kwargs):
    """FastMCP @mcp.tool() returns a FunctionTool wrapping the original;
    the original callable lives on `.fn`."""
    fn = getattr(tool_obj, "fn", tool_obj)
    return fn(*args, **kwargs)


def test_validate_mermaid_tool_valid_with_render_check_ok():
    with patch.object(mm, "_mermaid_render_check", return_value=(True, "")):
        result = _call_tool(mm.validate_mermaid, "graph TD\nA-->B")
    assert result["valid"] is True
    assert result["diagram_type"] == "graph"


def test_validate_mermaid_tool_invalid_due_to_render():
    with patch.object(mm, "_mermaid_render_check", return_value=(False, "syntax")):
        result = _call_tool(mm.validate_mermaid, "graph TD\nA-->B")
    assert result["valid"] is False
    assert any("mermaid_render_error" in e for e in result["errors"])


def test_validate_mermaid_tool_heuristic_invalid_skips_render():
    with patch.object(mm, "_mermaid_render_check") as render:
        result = _call_tool(mm.validate_mermaid, "")
    render.assert_not_called()
    assert result["valid"] is False


def test_fix_mermaid_tool_with_render_ok():
    with patch.object(mm, "_mermaid_render_check", return_value=(True, "")):
        result = _call_tool(mm.fix_mermaid, "graph TD\nA-->B")
    assert result["validation"]["valid"] is True
    assert result["fixed_code"]


def test_fix_mermaid_tool_with_render_error():
    with patch.object(mm, "_mermaid_render_check", return_value=(False, "bad")):
        result = _call_tool(mm.fix_mermaid, "graph TD\nA-->B")
    assert result["validation"]["valid"] is False
    assert any("mermaid_render_error" in e for e in result["validation"]["errors"])


def test_validate_mermaid_in_markdown_tool_no_blocks():
    result = _call_tool(mm.validate_mermaid_in_markdown, "no fenced blocks here")
    assert result["blocks_found"] == 0
    assert result["all_valid"] is True
    assert result["results"] == []


def test_validate_mermaid_in_markdown_tool_with_blocks():
    md = (
        "```mermaid\ngraph TD\nA-->B\n```\n"
        "```mermaid\nfoo\n```"
    )
    result = _call_tool(mm.validate_mermaid_in_markdown, md)
    assert result["blocks_found"] == 2
    assert result["all_valid"] is False
    assert len(result["results"]) == 2


def test_fix_mermaid_in_markdown_tool_rewrites_blocks():
    md = "intro\n```mermaid\nA --> B\n```\noutro"
    fake_validate = MagicMock(return_value={
        "blocks_found": 1, "all_valid": True, "results": [],
    })
    with (
        patch.object(mm, "_mermaid_render_check", return_value=(True, "")),
        patch.object(mm, "validate_mermaid_in_markdown", fake_validate),
    ):
        result = _call_tool(mm.fix_mermaid_in_markdown, md)
    assert result["blocks_found"] == 1
    assert "graph TD" in result["updated_markdown"]
    assert len(result["per_block_fixes"]) == 1


def test_fix_mermaid_in_markdown_tool_handles_empty():
    fake_validate = MagicMock(return_value={
        "blocks_found": 0, "all_valid": True, "results": [],
    })
    with patch.object(mm, "validate_mermaid_in_markdown", fake_validate):
        result = _call_tool(mm.fix_mermaid_in_markdown, "")
    assert result["blocks_found"] == 0
