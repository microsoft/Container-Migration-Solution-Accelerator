# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from utils.console_util import ConsoleColors, format_agent_message, get_role_style


class TestGetRoleStyle:
    @pytest.mark.parametrize(
        "agent_name",
        [
            "Chief Architect",
            "GKE Expert",
            "EKS Expert",
            "Azure Expert",
            "YAML Expert",
            "OpenShift Expert",
            "AKS Expert",
            "Rancher Expert",
            "Tanzu Expert",
            "OnPremK8s Expert",
            "Technical Writer",
            "QA Engineer",
        ],
    )
    def test_known_agents_return_styled_label_and_color(self, agent_name):
        label, color = get_role_style(agent_name)
        assert ConsoleColors.RESET in label
        assert color.startswith("\033[")

    def test_unknown_agent_returns_coordinator_default(self):
        label, color = get_role_style("Some Unknown Role")
        assert "COORDINATOR" in label
        assert color == ConsoleColors.WHITE

    def test_none_name_returns_coordinator_default(self):
        label, color = get_role_style(None)
        assert "COORDINATOR" in label
        assert color == ConsoleColors.WHITE


class TestFormatAgentMessage:
    def test_includes_role_and_content_and_resets(self):
        out = format_agent_message("Azure Expert", "hello", timestamp="")
        assert "AZURE EXPERT" in out
        assert "hello" in out
        assert ConsoleColors.RESET in out

    def test_appends_timestamp_when_provided(self):
        out = format_agent_message("Azure Expert", "hi", timestamp="12:00:00")
        assert "(12:00:00)" in out

    def test_truncates_long_content_with_ellipsis(self):
        content = "x" * 500
        out = format_agent_message("Azure Expert", content, "", max_content_length=10)
        assert "xxxxxxxxx…" in out

    def test_max_content_length_one_returns_single_ellipsis(self):
        out = format_agent_message("Azure Expert", "hello world", "", max_content_length=1)
        assert "…" in out

    def test_none_content_renders_as_empty(self):
        out = format_agent_message("Azure Expert", None, "")
        assert "AZURE EXPERT" in out

    def test_non_string_content_is_stringified(self):
        out = format_agent_message("Azure Expert", 12345, "")
        assert "12345" in out

    def test_max_content_length_disabled_when_zero(self):
        content = "x" * 50
        out = format_agent_message("Azure Expert", content, "", max_content_length=0)
        assert content in out
