from app import agents


def test_system_prompt_knows_the_time_zone_date_and_name():
    p = {"tz": "Asia/Kolkata", "uname": "Aaqhila", "tone": 60, "humor": 40, "formal": 30}
    sys = agents.build_system("chat", p, [], [])
    assert "Right now it is" in sys and "Asia/Kolkata" in sys and "Aaqhila" in sys


def test_bad_or_hostile_time_zone_falls_back_to_utc():
    for tz in ("Not/AZone", "../../etc/passwd", "", None, "x" * 500):
        line = agents.now_line({"tz": tz})
        assert "(UTC)" in line or "UTC" in line
    assert "name is" not in agents.now_line({"tz": "UTC", "uname": "   "})


def test_default_persona_carries_tz_and_name_to_the_backend():
    from app.turn import DEFAULT_PERSONA
    assert "tz" in DEFAULT_PERSONA and "uname" in DEFAULT_PERSONA
