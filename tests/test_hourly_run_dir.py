import pytest

from autofanpage.hourly_run_dir import HourlyRunDir


def test_hourly_run_dir_creates_timestamped_path(tmp_path):
    run_dir = HourlyRunDir.create(
        base=tmp_path,
        page="page_hourly_repost",
        run_label="2026-04-23T10-00-00Z",
    )

    assert (
        run_dir.path
        == tmp_path / "runs" / "page_hourly_repost" / "hourly" / "2026-04-23T10-00-00Z"
    )
    assert run_dir.path.exists()


@pytest.mark.parametrize("page", ["/tmp/escape", "../escape", "nested/../escape"])
def test_hourly_run_dir_rejects_non_local_page_segments(tmp_path, page):
    with pytest.raises(ValueError):
        HourlyRunDir.create(
            base=tmp_path,
            page=page,
            run_label="2026-04-23T10-00-00Z",
        )


@pytest.mark.parametrize("run_label", ["/tmp/escape", "../escape", "nested/../escape"])
def test_hourly_run_dir_rejects_non_local_run_label_segments(tmp_path, run_label):
    with pytest.raises(ValueError):
        HourlyRunDir.create(
            base=tmp_path,
            page="page_hourly_repost",
            run_label=run_label,
        )
