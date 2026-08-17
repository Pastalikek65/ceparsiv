from cepearsiv.markdownx import render_markdown


def test_render_heading_and_list():
    html = render_markdown("# Başlık\n- item1\n- item2")
    assert "<h1>Başlık</h1>" in html
    assert "<ul>" in html
    assert "<li>item1</li>" in html
    assert "<li>item2</li>" in html


def test_render_code_block():
    html = render_markdown("```python\nprint('hi')\n```")
    assert "<pre>" in html and "<code" in html
    assert "print(" in html
    assert "<em>" not in html

    html2 = render_markdown("```\n*italic* kod\n```")
    assert "<em>" not in html2
    assert "*italic* kod" in html2 or "*italic*" in html2


def test_render_escapes_script():
    html = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_escapes_img_onerror():
    html = render_markdown("<img src=x onerror=alert(1)>")
    assert "<img" not in html
    assert "&lt;img" in html


def test_render_blocks_javascript_links():
    html = render_markdown("[click](javascript:alert(1))")
    assert "<a" not in html
    assert 'href="javascript' not in html


def test_render_empty_and_none():
    assert render_markdown("") == ""
    assert render_markdown(None) == ""


def test_render_inline_code_not_processed():
    html = render_markdown("`code with *markdown*`")
    assert "<code>" in html
    assert "*markdown*" in html
    assert "<em>" not in html


def test_render_link_normal():
    html = render_markdown("[example](https://example.com)")
    assert 'href="https://example.com"' in html
    assert "example</a>" in html
