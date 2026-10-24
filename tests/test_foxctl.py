"""foxctl's reply handling and argument checks, against a scripted fake port."""

import pytest

import foxctl


class FakeSerial:
    """Stands in for serial.Serial: records writes, replays scripted lines."""

    def __init__(self, script):
        self.script = list(script)
        self.written = []
        self.port = "fake"

    def write(self, data):
        self.written.append(data.decode().strip())

    def readline(self):
        return (self.script.pop(0) + "\r\n").encode() if self.script else b""

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


@pytest.fixture
def fox(monkeypatch):
    def make(*replies):
        fake = FakeSerial(["OK FOXSINAD 0.2.0 REV3", *replies])
        monkeypatch.setattr(foxctl.serial, "Serial", lambda *a, **k: fake)
        monkeypatch.setattr(foxctl.time, "sleep", lambda s: None)
        f = foxctl.PicoFox(port="fake", timeout_s=0.2)
        return f, fake
    return make


def test_hello_is_checked_on_open(monkeypatch):
    monkeypatch.setattr(foxctl.serial, "Serial", lambda *a, **k: FakeSerial(["OK SOMETHING ELSE"]))
    monkeypatch.setattr(foxctl.time, "sleep", lambda s: None)
    with pytest.raises(foxctl.PicoFoxError, match="not foxsinad_fw"):
        foxctl.PicoFox(port="fake")


def test_ok_reply_and_command_text(fox):
    f, fake = fox("OK ATT 64")
    assert f.set_att(64) == "ATT 64"
    assert fake.written[-1] == "ATT 64"


def test_err_reply_raises(fox):
    f, _ = fox("ERR set CALL first")
    with pytest.raises(foxctl.PicoFoxError, match="set CALL first"):
        f.tone(1000, 3000)


def test_events_are_collected_not_returned(fox):
    f, _ = fox("*ID START", "*ID DONE", "OK OFF")
    assert f.off() == "OFF"
    assert f.events == ["*ID START", "*ID DONE"]


def test_timeout_raises(fox):
    f, _ = fox()  # no reply at all
    with pytest.raises(foxctl.PicoFoxError, match="no reply"):
        f.status()


def test_status_parses_to_dict(fox):
    f, _ = fox("OK STATUS mode=TONE freq=145.550000 att=40 tone=1000 dev=3000 "
               "call=N0CALL rev=3 since_id=20 up=336")
    st = f.status()
    assert st["mode"] == "TONE" and st["att"] == "40" and st["call"] == "N0CALL"


@pytest.mark.parametrize("method,args", [
    ("set_att", (128,)), ("set_att", (-1,)), ("set_att", (12.5,)),
    ("set_freq", (143.9,)), ("set_freq", (148.0,)),
    ("tone", (99, 3000)), ("tone", (1000, 10001)),
])
def test_out_of_range_never_reaches_the_port(fox, method, args):
    # The firmware parses junk as 0 (ATT 0 = full power), so the host must refuse.
    f, fake = fox()
    sent_before = list(fake.written)
    with pytest.raises(foxctl.PicoFoxError):
        getattr(f, method)(*args)
    assert fake.written == sent_before
