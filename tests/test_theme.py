"""Dark-mode plumbing: the boot script and toggle ship on every page."""


def test_theme_boot_script_in_head(client):
    html = client.get("/").get_data(as_text=True)
    assert "js/theme.js" in html


def test_theme_toggle_button_present(client):
    html = client.get("/").get_data(as_text=True)
    assert 'data-role="theme-toggle"' in html
    assert "mt-theme-icon-moon" in html
    assert "mt-theme-icon-sun" in html
