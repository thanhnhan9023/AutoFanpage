from autofanpage.templates import TEMPLATES, POST_TYPE_BY_SLOT, slot_time


def test_all_four_types_present():
    assert set(TEMPLATES.keys()) == {"news", "guide", "opinion", "case_study"}


def test_slot_index_to_type_matches_spec():
    assert POST_TYPE_BY_SLOT == ("news", "guide", "opinion", "case_study")


def test_each_template_has_required_fields():
    for t, tpl in TEMPLATES.items():
        assert tpl["hook_shape"]
        assert tpl["body_shape"]
        assert tpl["cta"]
        assert tpl["hashtag_hint"]
        assert tpl["first_comment_shape"]


def test_slot_time_reads_profile_list():
    post_times = ["07:30", "11:45", "15:00", "19:20"]
    assert slot_time(post_times, 0) == "07:30"
    assert slot_time(post_times, 3) == "19:20"


def test_slot_time_out_of_range_raises():
    import pytest
    with pytest.raises(IndexError):
        slot_time(["08:00"], 3)
