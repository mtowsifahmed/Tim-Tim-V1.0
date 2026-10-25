import pytest

from app import skills


def ok(name, args, agent="chat", expect=None):
    out = skills.validate(name, args, agent)
    if expect is not None:
        assert out == expect
    return out


def test_new_read_only_and_info_skills():
    ok("system_info", {}, "chat", {})
    ok("clipboard_read", {}, "coding", {})
    ok("list_dir", {"path": "C:\\Users\\me\\Documents"}, "coding", {"path": "C:\\Users\\me\\Documents"})
    ok("search_web", {"query": "best pizza near me"}, "research", {"query": "best pizza near me"})
    ok("open_path", {"path": "C:\\Users\\me\\Downloads"}, "chat")
    ok("lock_screen", {}, "chat")


def test_file_skills_validate_paths_and_refuse_traversal():
    ok("copy_file", {"from": "C:\\a\\x.txt", "to": "C:\\b\\x.txt"}, "coding", {"from": "C:\\a\\x.txt", "to": "C:\\b\\x.txt"})
    ok("move_file", {"from": "/tmp/a.txt", "to": "/tmp/b.txt"}, "coding")
    ok("delete_file", {"path": "C:\\a\\old.txt"}, "coding")
    ok("create_folder", {"path": "C:\\Projects\\new"}, "creative")
    for bad in ({"path": "C:\\a\\..\\..\\Windows"}, {"path": "C:\\a\\b*.txt"}, {"path": "a|b"}, {"path": ""}, {}):
        with pytest.raises(ValueError):
            skills.validate("delete_file", bad, "coding")
    with pytest.raises(ValueError):
        skills.validate("copy_file", {"from": "x", "to": "C:\\..\\y"}, "coding")


def test_reminders_media_and_clipboard_arguments():
    ok("set_reminder", {"minutes": 30, "message": "stretch"}, "planner", {"minutes": 30, "message": "stretch"})
    ok("set_reminder", {"minutes": "45", "message": "tea"}, "chat", {"minutes": 45, "message": "tea"})
    for bad in ({"minutes": 0, "message": "x"}, {"minutes": 2000, "message": "x"}, {"minutes": 5, "message": ""}, {"minutes": 1.5, "message": "x"}, {"minutes": True, "message": "x"}):
        with pytest.raises(ValueError):
            skills.validate("set_reminder", bad, "planner")
    assert ok("media_key", {"key": "Volume_Up", "times": 5}, "chat") == {"key": "volume_up", "times": 5}
    assert ok("media_key", {"key": "mute"}, "chat") == {"key": "mute"}                         # `times` is optional
    for bad in ({"key": "power"}, {"key": "volume_up", "times": 100}, {"key": "volume_up", "times": 0}):
        with pytest.raises(ValueError):
            skills.validate("media_key", bad, "chat")
    ok("clipboard_write", {"text": "multi\nline text"}, "research")
    with pytest.raises(ValueError):
        skills.validate("clipboard_write", {"text": "a\x00b"}, "research")


def test_each_agent_only_gets_the_tools_it_needs():
    for name, agents in [("run_shell", "research"), ("delete_file", "chat"), ("delete_file", "planner"), ("write_file", "planner"), ("lock_screen", "coding"), ("set_reminder", "coding")]:
        with pytest.raises(ValueError):
            skills.validate(name, {"command": "x", "path": "C:\\x", "content": "x", "minutes": 5, "message": "m"}, agents)
    assert all(s in skills.SKILLS for ss in skills.AGENT_SKILLS.values() for s in ss)             # no typos in the allow-lists


def test_catalog_lists_every_skill_and_marks_optional_args():
    text = skills.catalog_for_prompt()
    assert all(n in text for n in skills.SKILLS) and "times?" in text
