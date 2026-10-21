from veille_pipeline.ats import detect_ats


def test_detects_by_url_and_html():
    assert detect_ats("https://apply.workable.com/exotec/", "") == ["workable"]
    html = '<script src="https://static.teamtailor-cdn.com/x.js"></script>'
    assert detect_ats("https://carrieres.example.org/jobs", html) == ["teamtailor"]
    assert detect_ats("https://x.example", "https://jobs.smartrecruiters.com/Kiabi") == ["smartrecruiters"]


def test_cms_is_listed_last_and_unknown_is_empty():
    html = '<link href="/wp-content/a.css"><a href="https://jobs.lever.co/acme">x</a>'
    assert detect_ats("https://x.example", html) == ["lever", "wordpress"]
    assert detect_ats("https://x.example", "<html>rien</html>") == []
