# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from utils.prompt_util import TemplateUtility


class TestTemplateUtility:
    def test_render_substitutes_variables(self):
        out = TemplateUtility.render("Hello {{ name }}!", name="Ada")
        assert out == "Hello Ada!"

    def test_render_with_no_placeholders_returns_original(self):
        out = TemplateUtility.render("plain text")
        assert out == "plain text"

    def test_render_supports_multiple_variables(self):
        out = TemplateUtility.render("{{ a }} + {{ b }} = {{ c }}", a=1, b=2, c=3)
        assert out == "1 + 2 = 3"

    def test_render_from_file_reads_and_renders(self, tmp_path):
        f = tmp_path / "template.txt"
        f.write_text("Hi {{ user }}", encoding="utf-8")
        out = TemplateUtility.render_from_file(str(f), user="bob")
        assert out == "Hi bob"

    def test_render_supports_loops(self):
        tpl = "{% for x in items %}{{ x }},{% endfor %}"
        out = TemplateUtility.render(tpl, items=[1, 2, 3])
        assert out == "1,2,3,"
