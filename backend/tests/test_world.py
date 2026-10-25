from app.routes.world import parse_rss, parse_usgs

USGS = {"features": [
    {"properties": {"mag": 5.8, "place": "Off the coast of Japan", "time": 1000}, "geometry": {"coordinates": [142.1, 36.2, 10]}},
    {"properties": {"mag": 4.6, "place": "Alaska", "time": 2000}, "geometry": {"coordinates": [-150.0, 61.0, 30]}},
    {"properties": {"mag": None, "place": "bad"}, "geometry": {"coordinates": [1, 2]}},
    {"properties": {"mag": 5.0, "place": "no coords"}, "geometry": {"coordinates": []}}]}

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>First story</title><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>  </title></item>
<item><title>Second story</title><pubDate>garbage</pubDate></item></channel></rss>"""


def test_usgs_parsing_skips_bad_rows_and_sorts_newest_first():
    ev = parse_usgs(USGS)
    assert [e["title"] for e in ev] == ["Alaska", "Off the coast of Japan"]
    assert ev[1]["lat"] == 36.2 and ev[1]["lon"] == 142.1 and ev[1]["mag"] == 5.8


def test_rss_parsing_handles_blank_titles_and_bad_dates():
    h = parse_rss(RSS)
    assert [x["title"] for x in h] == ["First story", "Second story"]
    assert h[0]["time"] == 1791799200000 and h[1]["time"] > 0 and h[0]["source"] == "BBC News"


def test_rss_rejects_entity_bomb():
    import pytest
    bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><rss><channel><item><title>&b;</title></item></channel></rss>'
    with pytest.raises(Exception):
        parse_rss(bomb)
