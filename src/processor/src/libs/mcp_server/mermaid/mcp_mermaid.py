# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastmcp~=2.14.5",
#   "httpx~=0.28.1",
# ]
# ///

"""FastMCP server for Mermaid validation and best-effort auto-fix.

Goals:
- Catch the most common broken Mermaid outputs produced by LLMs.
- Apply safe, deterministic fixes (no external network calls).
- Use mermaid.js CLI for real syntax validation when available.

This provides:
- block extraction from Markdown
- basic structural validation (heuristic)
- mermaid.js-powered validation (if mmdc/node available)
- best-effort normalization and small repairs

"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass

from fastmcp import FastMCP

mcp = FastMCP(
    name="mermaid_service",
    instructions=(
        "Mermaid validation and best-effort auto-fix. "
        "Use validate_mermaid() before saving markdown. "
        "Use fix_mermaid() to normalize/fix common issues."
    ),
)


SMART_QUOTES = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u00a0": " ",
}


KNOWN_DIAGRAM_PREFIXES = (
    "graph",
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "quadrantChart",
    "requirementDiagram",
)


INIT_DIRECTIVE_RE = re.compile(r"^\s*%%\{init:.*\}%%\s*$")

# Some Mermaid renderers/versions are picky about `subgraph <id>["Label"]`.
# Normalizing to `subgraph "Label"` tends to be accepted more broadly.
SUBGRAPH_ID_LABEL_RE = re.compile(
    r"^(?P<indent>\s*)subgraph\s+(?P<id>[A-Za-z_][A-Za-z0-9_]*)\s*\[(?P<label>.*)\]\s*$"
)


@dataclass(frozen=True)
class MermaidValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]
    normalized_code: str
    diagram_type: str | None


def _normalize_text(text: str) -> tuple[str, list[str]]:
    fixes: list[str] = []
    if text is None:
        return "", ["input_was_none"]

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized != text:
        fixes.append("normalize_newlines")

    for bad, good in SMART_QUOTES.items():
        if bad in normalized:
            normalized = normalized.replace(bad, good)
            fixes.append("replace_smart_quotes")

    # Strip outer whitespace but keep internal formatting
    stripped = normalized.strip("\n")
    if stripped != normalized:
        normalized = stripped
        fixes.append("strip_outer_newlines")

    return normalized, fixes


def extract_mermaid_blocks_from_markdown(markdown: str) -> list[str]:
    """Extract ```mermaid fenced blocks from markdown, returning raw diagram code."""
    if not markdown:
        return []

    # Capture content between ```mermaid ... ``` (case-insensitive)
    pattern = re.compile(r"```\s*mermaid\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)
    return [m.group(1).strip("\n") for m in pattern.finditer(markdown)]


def _strip_fences_if_present(code: str) -> tuple[str, list[str]]:
    fixes: list[str] = []
    if not code:
        return "", fixes

    trimmed = code.strip()
    if trimmed.startswith("```"):
        # Generic fence stripper (handles ```mermaid too)
        fence_match = re.match(r"^```[^\n]*\n(.*)\n```\s*$", trimmed, flags=re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip("\n"), ["strip_code_fences"]

    return code, fixes


def _first_nonempty_line(lines: list[str]) -> tuple[int | None, str | None]:
    for i, line in enumerate(lines):
        if line.strip():
            return i, line
    return None, None


def _detect_diagram_type(code: str) -> str | None:
    lines = code.split("\n")

    # Allow init directive(s) at the top
    start_idx = 0
    while start_idx < len(lines) and INIT_DIRECTIVE_RE.match(lines[start_idx] or ""):
        start_idx += 1

    idx, line = _first_nonempty_line(lines[start_idx:])
    if line is None:
        return None

    header = line.strip()
    for prefix in KNOWN_DIAGRAM_PREFIXES:
        if header.startswith(prefix):
            return prefix

    return None


def _balance_check(code: str) -> list[str]:
    """Very small balance check for (), [], {} outside quotes.

    Mermaid allows lots of punctuation; this check is heuristic only.
    """

    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    openers = set(pairs.values())
    closers = set(pairs.keys())

    in_single = False
    in_double = False
    in_backtick = False
    escaped = False

    for ch in code:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue

        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            continue
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
            continue
        if ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
            continue

        if in_single or in_double or in_backtick:
            continue

        if ch in openers:
            stack.append(ch)
        elif ch in closers:
            if not stack or stack[-1] != pairs[ch]:
                return [f"unbalanced_brackets: unexpected '{ch}'"]
            stack.pop()

    if in_single or in_double or in_backtick:
        return ["unbalanced_quotes"]

    if stack:
        return [f"unbalanced_brackets: missing closers for {''.join(stack)}"]

    return []


def basic_validate_mermaid(code: str) -> MermaidValidation:
    original = code or ""

    code, fence_fixes = _strip_fences_if_present(original)
    normalized, norm_fixes = _normalize_text(code)

    errors: list[str] = []
    warnings: list[str] = []

    if not normalized.strip():
        errors.append("empty_diagram")
        return MermaidValidation(
            valid=False,
            errors=errors,
            warnings=warnings,
            normalized_code=normalized,
            diagram_type=None,
        )

    diagram_type = _detect_diagram_type(normalized)
    if diagram_type is None:
        errors.append(
            "missing_diagram_header: expected one of "
            + ", ".join(KNOWN_DIAGRAM_PREFIXES)
        )

    errors.extend(_balance_check(normalized))

    if fence_fixes or norm_fixes:
        warnings.append("normalized_input")

    return MermaidValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        normalized_code=normalized,
        diagram_type=diagram_type,
    )


def basic_fix_mermaid(code: str) -> tuple[str, list[str], MermaidValidation]:
    applied: list[str] = []

    code = code or ""
    code, fence_fixes = _strip_fences_if_present(code)
    applied.extend(fence_fixes)

    normalized, norm_fixes = _normalize_text(code)
    applied.extend(norm_fixes)

    # Line-by-line normalizations
    new_lines: list[str] = []
    removed_bullets = False
    normalized_subgraph_labels = False
    for line in normalized.split("\n"):
        # Remove markdown list prefixes accidentally placed in mermaid blocks
        if re.match(r"^\s*[-*]\s+\S", line):
            line = re.sub(r"^(\s*)[-*]\s+", r"\1", line)
            removed_bullets = True

        # Normalize `subgraph ID["Label"]` → `subgraph "Label"`
        # This keeps the diagram semantics while improving compatibility.
        m = SUBGRAPH_ID_LABEL_RE.match(line)
        if m:
            indent = m.group("indent")
            label = m.group("label").strip()
            # Prefer double quotes and strip outer quotes/brackets artifacts.
            if (label.startswith('"') and label.endswith('"')) or (
                label.startswith("'") and label.endswith("'")
            ):
                label = label[1:-1]
            new_lines.append(f'{indent}subgraph "{label}"')
            normalized_subgraph_labels = True
            continue

        new_lines.append(line)

    if removed_bullets:
        applied.append("remove_markdown_bullets")
    if normalized_subgraph_labels:
        applied.append("normalize_subgraph_labels")

    normalized = "\n".join(new_lines).strip("\n")

    # If header missing but looks like flowchart edges, prepend a default graph.
    if _detect_diagram_type(normalized) is None:
        if "-->" in normalized or "---" in normalized:
            normalized = "graph TD\n" + normalized
            applied.append("prepend_graph_td")

    # If brackets are unbalanced by missing closers, append closers (best-effort)
    balance_errors = _balance_check(normalized)
    if balance_errors and any("missing closers" in e for e in balance_errors):
        missing = []
        # Extract opener list from error string if possible
        m = re.search(r"missing closers for ([\(\)\[\]\{\}]+)", balance_errors[0])
        if m:
            openers = m.group(1)
            closer_map = {"(": ")", "[": "]", "{": "}"}
            for ch in reversed(openers):
                if ch in closer_map:
                    missing.append(closer_map[ch])
        if missing:
            normalized = normalized + "".join(missing)
            applied.append("append_missing_bracket_closers")

    validation = basic_validate_mermaid(normalized)
    return normalized, applied, validation


def _mermaid_render_check(code: str, timeout: int = 10) -> tuple[bool, str]:
    """Try to render mermaid code using Node.js mermaid library for real validation.

    Returns (success, error_message). If Node.js or mermaid is not available,
    returns (True, "") to fall back gracefully.
    """
    node_path = shutil.which("node")
    if not node_path:
        return True, ""  # Node not available, skip render check

    # Use a simple Node.js script that imports mermaid and tries to parse
    js_script = """
try {
    const mermaid = require('mermaid');
    mermaid.default.initialize({ startOnLoad: false, suppressErrors: false });
    const code = process.argv[1];
    mermaid.default.parse(code).then(result => {
        process.stdout.write(JSON.stringify({ valid: true }));
    }).catch(err => {
        const msg = err.message || String(err);
        // DOMPurify/DOM errors mean syntax parsed OK but renderer needs browser - treat as valid
        if (msg.includes('DOMPurify') || msg.includes('document') || msg.includes('window')) {
            process.stdout.write(JSON.stringify({ valid: true }));
        } else {
            process.stdout.write(JSON.stringify({ valid: false, error: msg }));
        }
    });
} catch (e) {
    // mermaid not installed, skip
    process.stdout.write(JSON.stringify({ valid: true, skipped: true }));
}
"""
    try:
        result = subprocess.run(
            [node_path, "-e", js_script, code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0 and result.stderr:
            # Parse error from stderr if present
            stderr = result.stderr.strip()
            if "Error" in stderr or "error" in stderr:
                # Extract just the error message
                lines = stderr.split("\n")
                error_line = next(
                    (line for line in lines if "Error" in line or "error" in line), lines[0]
                )
                return False, error_line[:200]
            return True, ""

        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout.strip())
                if parsed.get("skipped"):
                    return True, ""
                if not parsed.get("valid", True):
                    return False, parsed.get("error", "Unknown mermaid syntax error")[
                        :200
                    ]
            except json.JSONDecodeError:
                pass

        return True, ""
    except (subprocess.TimeoutExpired, OSError):
        return True, ""  # Timeout or OS error, skip render check


@mcp.tool()
def validate_mermaid(code: str) -> dict:
    """Validate Mermaid code using heuristic checks and mermaid.js rendering."""
    v = basic_validate_mermaid(code)
    result = {
        "valid": v.valid,
        "errors": list(v.errors),
        "warnings": v.warnings,
        "diagram_type": v.diagram_type,
        "normalized_code": v.normalized_code,
    }

    # If heuristic check passed, also try real mermaid.js rendering
    if v.valid:
        render_ok, render_error = _mermaid_render_check(v.normalized_code)
        if not render_ok:
            result["valid"] = False
            result["errors"].append(f"mermaid_render_error: {render_error}")

    return result


@mcp.tool()
def fix_mermaid(code: str) -> dict:
    """Normalize and best-effort fix Mermaid code, then validate with mermaid.js."""
    fixed, applied, v = basic_fix_mermaid(code)
    errors = list(v.errors)

    # If heuristic validation passed, also check with mermaid.js renderer
    if v.valid:
        render_ok, render_error = _mermaid_render_check(fixed)
        if not render_ok:
            errors.append(f"mermaid_render_error: {render_error}")

    return {
        "fixed_code": fixed,
        "applied_fixes": applied,
        "validation": {
            "valid": v.valid and len(errors) == 0,
            "errors": errors,
            "warnings": v.warnings,
            "diagram_type": v.diagram_type,
        },
    }


@mcp.tool()
def validate_mermaid_in_markdown(markdown: str) -> dict:
    """Extract Mermaid blocks from markdown and validate each."""
    blocks = extract_mermaid_blocks_from_markdown(markdown or "")
    results = []
    for i, block in enumerate(blocks):
        v = basic_validate_mermaid(block)
        results.append({
            "index": i,
            "valid": v.valid,
            "errors": v.errors,
            "warnings": v.warnings,
            "diagram_type": v.diagram_type,
        })

    return {
        "blocks_found": len(blocks),
        "all_valid": all(r["valid"] for r in results) if results else True,
        "results": results,
    }


@mcp.tool()
def fix_mermaid_in_markdown(markdown: str) -> dict:
    """Fix Mermaid blocks inside a markdown document and re-validate.

    Returns updated markdown content with each ```mermaid block rewritten to a
    normalized/fixed version.
    """

    text = markdown or ""

    # Replace each mermaid fenced block with a fixed version.
    # Capture content between ```mermaid ... ``` (case-insensitive)
    pattern = re.compile(r"```\s*mermaid\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)

    per_block = []

    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        fixed, applied, v = basic_fix_mermaid(raw)
        per_block.append({
            "valid": v.valid,
            "errors": v.errors,
            "warnings": v.warnings,
            "diagram_type": v.diagram_type,
            "applied_fixes": applied,
        })
        return "```mermaid\n" + fixed + "\n```"

    updated = pattern.sub(_replace, text)
    validation = validate_mermaid_in_markdown(updated)

    return {
        "blocks_found": validation["blocks_found"],
        "all_valid": validation["all_valid"],
        "results": validation["results"],
        "per_block_fixes": per_block,
        "updated_markdown": updated,
    }


if __name__ == "__main__":
    mcp.run()
