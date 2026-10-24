"""flash.py's bootloader-drive detection, on temporary directories."""

import flash


def test_finds_the_rp2040_drive(tmp_path, monkeypatch):
    other, rp2 = tmp_path / "USBSTICK", tmp_path / "RPI-RP2"
    other.mkdir(); rp2.mkdir()
    (rp2 / "INFO_UF2.TXT").write_text("UF2 Bootloader v3.0\nModel: Raspberry Pi RP2\nBoard-ID: RPI-RP2\n")
    monkeypatch.setattr(flash, "_candidate_mounts", lambda: [str(other), str(rp2)])
    assert flash.find_bootloader_drive() == str(rp2)


def test_ignores_other_uf2_boards(tmp_path, monkeypatch):
    d = tmp_path / "OTHER"
    d.mkdir()
    (d / "INFO_UF2.TXT").write_text("UF2 Bootloader\nBoard-ID: SAMD21-Something\n")
    monkeypatch.setattr(flash, "_candidate_mounts", lambda: [str(d)])
    assert flash.find_bootloader_drive() is None


# --- stock firmware selection -------------------------------------------

def test_git_blob_sha_matches_git():
    # Values from `git hash-object` (an empty file, and "hello\n").
    assert flash.git_blob_sha(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    assert flash.git_blob_sha(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def _remote(name, sha, date="2026-08-07"):
    return {"name": name, "size": 3, "sha": sha, "url": f"https://x/{name}", "date": date}


def test_choices_mark_new_changed_and_same():
    remote = [_remote("pfoxr3v1.uf2", "aaa"), _remote("pfoxr3-forceformat.uf2", "bbb")]
    local = {"pfoxr3v1.uf2": ("stock/pfoxr3v1.uf2", "old")}
    choices, suggest = flash.stock_choices(remote, local)
    by = {(c["name"], c["url"] is None): c["status"] for c in choices}
    assert by[("pfoxr3v1.uf2", False)] == "changed since your saved copy"
    assert by[("pfoxr3-forceformat.uf2", False)] == "new: not downloaded yet"
    assert by[("pfoxr3v1.uf2", True)] == "your saved copy"   # still offered
    assert choices[suggest]["name"] == "pfoxr3v1.uf2"


def test_identical_copy_is_offered_once_without_download():
    remote = [_remote("pfoxr3v1.uf2", "aaa")]
    local = {"pfoxr3v1.uf2": ("stock/pfoxr3v1.uf2", "aaa")}
    choices, _ = flash.stock_choices(remote, local)
    assert len(choices) == 1
    assert choices[0]["status"] == "same as your saved copy"
    assert choices[0]["path"] == "stock/pfoxr3v1.uf2"


def test_suggestion_skips_forceformat_even_if_listed_first():
    remote = [_remote("pfoxr3-forceformat.uf2", "bbb", "2026-09-01"),
              _remote("pfoxr3v1.uf2", "aaa", "2026-08-07")]
    choices, suggest = flash.stock_choices(remote, {})
    assert choices[0]["name"] == "pfoxr3-forceformat.uf2"   # newest first
    assert choices[suggest]["name"] == "pfoxr3v1.uf2"


def test_offline_offers_saved_copies():
    local = {"pfoxr3v1.uf2": ("stock/pfoxr3v1.uf2", "aaa")}
    choices, _ = flash.stock_choices([], local, online=False)
    assert [c["status"] for c in choices] == ["your saved copy"]


def test_copy_removed_from_github_is_flagged():
    remote = [_remote("pfoxr3v2.uf2", "ccc")]
    local = {"pfoxr3v1.uf2": ("stock/pfoxr3v1.uf2", "aaa")}
    choices, _ = flash.stock_choices(remote, local, online=True)
    assert choices[-1]["status"] == "your saved copy (no longer on GitHub)"
