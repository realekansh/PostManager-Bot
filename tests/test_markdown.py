from bot.utils.markdown import render_user_content


def test_plain_text_keeps_punctuation() -> None:
    rendered = render_user_content("Hello, world! This stays plain.")
    assert rendered == "Hello, world! This stays plain."


def test_nested_formatting_renders() -> None:
    rendered = render_user_content("*Bold _italic_ text*")
    assert rendered == "<b>Bold <i>italic</i> text</b>"


def test_text_link_renders() -> None:
    rendered = render_user_content("Read [Docs](https://example.com) now")
    assert rendered == 'Read <a href="https://example.com">Docs</a> now'


def test_link_inside_formatted_text_renders() -> None:
    rendered = render_user_content("*Read [Docs](https://example.com) now*")
    assert rendered == '<b>Read <a href="https://example.com">Docs</a> now</b>'


def test_spoiler_underline_and_strikethrough_render() -> None:
    rendered = render_user_content("__Heads up__ ||secret|| ~old~")
    assert rendered == "<u>Heads up</u> <tg-spoiler>secret</tg-spoiler> <s>old</s>"


def test_inline_and_block_code_render() -> None:
    rendered = render_user_content("`print(1)`\n```python\nhello\n```")
    assert rendered == "<code>print(1)</code>\n<pre><code>hello</code></pre>"


def test_blockquote_renders() -> None:
    rendered = render_user_content("> quoted line\n> second line\nnormal line")
    assert rendered == "<blockquote>quoted line\nsecond line</blockquote>\nnormal line"
