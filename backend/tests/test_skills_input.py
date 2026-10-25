import pytest

from app import skills


def test_typing_clicking_and_key_skills_are_validated():
    assert skills.validate("type_text", {"text": "hello\nworld"}, "coding") == {"text": "hello\nworld"}
    assert skills.validate("press_key", {"key": " Ctrl+S "}, "coding") == {"key": "ctrl+s"}
    assert skills.validate("click", {"x": "120", "y": 300}, "chat") == {"x": 120, "y": 300}
    for name, args, agent in [("press_key", {"key": "win+r"}, "coding"), ("click", {"x": -5, "y": 1}, "chat"), ("click", {"x": 1.5, "y": 1}, "chat"),
                              ("click", {"x": True, "y": 1}, "chat"), ("type_text", {"text": "x" * 3000}, "coding"), ("click", {"x": 1, "y": 1}, "research"),
                              ("type_text", {"text": "a\x00b"}, "coding")]:
        with pytest.raises(ValueError):
            skills.validate(name, args, agent)
