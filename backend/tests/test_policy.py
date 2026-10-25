from app import policy as p


def test_owner_and_moderator_bypass_caps():
    assert p.daily_cap("owner", 30, 100) is None
    assert p.daily_cap("moderator", 30, 100) is None
    assert p.daily_cap("free", 30, 100) == 30
    assert p.daily_cap("pro", 30, 100) == 100


def test_byok_is_pro_or_staff_only():
    assert not p.can_use_byok("free")
    assert all(p.can_use_byok(r) for r in ("pro", "moderator", "owner"))


def test_moderator_can_grant_pro_to_ordinary_users_only():
    assert p.can_change_plan("moderator", "free")
    assert p.can_change_plan("moderator", "pro")
    assert not p.can_change_plan("moderator", "owner")
    assert not p.can_change_plan("moderator", "moderator")
    assert not p.can_change_plan("free", "free")
    assert not p.can_change_plan("pro", "free")


def test_only_owner_manages_moderators_and_owner_is_untouchable():
    assert p.can_set_moderator("owner", "free", True)
    assert p.can_set_moderator("owner", "moderator", False)
    assert not p.can_set_moderator("owner", "owner", True)
    assert not p.can_set_moderator("owner", "owner", False)
    assert not p.can_set_moderator("moderator", "free", True)
    assert not p.can_set_moderator("moderator", "moderator", False)
    assert not p.can_set_moderator("owner", "moderator", True)   # already one
    assert not p.can_set_moderator("owner", "free", False)       # not a moderator


def test_role_after_demotion_follows_plan():
    assert p.role_after_moderator_removed("pro") == "pro"
    assert p.role_after_moderator_removed("free") == "free"
