from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).resolve().parents[2] / "app" / "pages"
FORBIDDEN = ("unsafe_allow_html", "<style", "st.html(", "st.spinner")


@pytest.mark.parametrize("path", sorted(PAGES_DIR.rglob("*.py")), ids=lambda p: str(p.relative_to(PAGES_DIR)))
def test_pages_do_not_style_or_spin(path):
    source = path.read_text()
    found = [token for token in FORBIDDEN if token in source]
    assert not found, f"{path}: {found} — CSS lives only in app/shell, loading uses shell.skeleton"


def test_css_has_no_tag_like_text():
    # st.html sanitizes the injected <style>; any "<word" in it (even in a comment) drops the whole sheet
    styles = Path(__file__).resolve().parents[2] / "app" / "shell" / "styles"
    for path in styles.glob("*.css"):
        assert "<" not in path.read_text(encoding="utf-8"), path
