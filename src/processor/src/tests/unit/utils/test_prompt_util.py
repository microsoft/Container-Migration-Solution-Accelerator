# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""Tests for the TemplateUtility prompt rendering helpers."""

import pytest

from utils.prompt_util import TemplateUtility


class TestRender:
    def test_render_substitutes_simple_variable(self):
        out = TemplateUtility.render("Hello {{ name }}!", name="World")
        assert out == "Hello World!"

    def test_render_supports_loops_and_conditionals(self):
        tmpl = "{% for i in items %}{{ i }}{% if not loop.last %},{% endif %}{% endfor %}"
        out = TemplateUtility.render(tmpl, items=["a", "b", "c"])
        assert out == "a,b,c"

    def test_render_returns_template_unchanged_when_no_placeholders(self):
        out = TemplateUtility.render("static text")
        assert out == "static text"

    def test_render_missing_variable_renders_as_empty_string(self):
        # Jinja2 default Undefined renders as empty string.
        out = TemplateUtility.render("Hello {{ missing }}!")
        assert out == "Hello !"


class TestRenderFromFile:
    def test_render_from_file_reads_and_renders(self, tmp_path):
        path = tmp_path / "tmpl.j2"
        path.write_text("Hi {{ user }}", encoding="utf-8")

        out = TemplateUtility.render_from_file(str(path), user="Alice")

        assert out == "Hi Alice"

    def test_render_from_file_supports_unicode_template(self, tmp_path):
        path = tmp_path / "unicode.j2"
        path.write_text("héllo {{ name }} 🚀", encoding="utf-8")

        out = TemplateUtility.render_from_file(str(path), name="Zoë")

        assert out == "héllo Zoë 🚀"

    def test_render_from_file_raises_when_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TemplateUtility.render_from_file(str(tmp_path / "nope.j2"))
