from lxml import html


def strip_html(s):
    return str(html.fromstring(s).text_content())
