# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for utils.console_util formatting helpers."""

import pytest

from utils.console_util import (
    ConsoleColors,
    format_agent_message,
    get_role_style,
)


class TestGetRoleStyle:
    @pytest.mark.parametrize(
        "name,color_token",
        [
            ("Chief Architect", ConsoleColors.MAGENTA),
            ("GKE Expert", ConsoleColors.GREEN),
            ("EKS Expert", ConsoleColors.YELLOW),
            ("Azure Expert", ConsoleColors.CYAN),
            ("YAML Expert", ConsoleColors.WHITE),
            ("OpenShift Expert", ConsoleColors.BLUE),
            ("AKS Expert", ConsoleColors.RED),
            ("Rancher Expert", ConsoleColors.DARK_MAGENTA),
            ("Tanzu Expert", ConsoleColors.DARK_GREEN),
            ("OnPremK8s Expert", ConsoleColors.DARK_YELLOW),
            ("Technical Writer", ConsoleColors.DARK_CYAN),
            ("QA Engineer", ConsoleColors.DARK_BLUE),
        ],
    )
    def test_returns_known_role_styling(self, name, color_token):
        label, color = get_role_style(name)
        assert color == color_token
        assert color_token in label
        assert ConsoleColors.BOLD in label
        assert label.endswith(ConsoleColors.RESET)

    def test_unknown_role_falls_back_to_coordinator(self):
        label, color = get_role_style("Some Random Role")
        assert color == ConsoleColors.WHITE
        assert "COORDINATOR" in label

    def test_none_name_falls_back_to_coordinator(self):
        label, color = get_role_style(None)
        assert color == ConsoleColors.WHITE
        assert "COORDINATOR" in label

    def test_default_argument_falls_back_to_coordinator(self):
        label, color = get_role_style()
        assert color == ConsoleColors.WHITE
        assert "COORDINATOR" in label


class TestFormatAgentMessage:
    def test_formats_message_with_timestamp(self):
        out = format_agent_message("Azure Expert", "hello there", "12:34")
        assert "AZURE EXPERT" in out
        assert "hello there" in out
        assert "(12:34)" in out

    def test_omits_timestamp_when_falsy(self):
        out = format_agent_message("Azure Expert", "hi", "")
        assert "()" not in out
        assert "hi" in out

    def test_none_content_renders_as_empty(self):
        out = format_agent_message("Azure Expert", None, None)
        # Content becomes empty string and is wrapped in color codes.
        assert "AZURE EXPERT" in out
        assert "None" not in out

    def test_long_content_is_truncated_with_ellipsis(self):
        content = "x" * 50
        out = format_agent_message("Azure Expert", content, None, max_content_length=10)
        # 9 chars of content + ellipsis
        assert "x" * 9 + "…" in out
        assert "x" * 10 not in out  # ensure not the full ten characters

    def test_content_below_limit_is_not_truncated(self):
        out = format_agent_message("Azure Expert", "short", None, max_content_length=100)
        assert "short" in out
        assert "…" not in out

    def test_max_length_one_replaces_with_single_ellipsis(self):
        out = format_agent_message("Azure Expert", "abcdef", None, max_content_length=1)
        assert "…" in out
        # Original content must not appear in full.
        assert "abcdef" not in out

    def test_non_int_max_length_disables_truncation(self):
        long_content = "y" * 200
        out = format_agent_message(
            "Azure Expert", long_content, None, max_content_length=None
        )
        assert long_content in out

    def test_non_string_content_is_stringified(self):
        out = format_agent_message("Azure Expert", 12345, None)
        assert "12345" in out

    def test_unknown_role_uses_coordinator_label(self):
        out = format_agent_message("Mystery", "msg", None)
        assert "COORDINATOR" in out
