import plistlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ipakit import profile
from ipakit.provisioner import Credentials
from ipakit.service import Ipakit
from ipakit.store import Store


def make_profile(path: Path, expires: datetime, udids=("UDID1",)) -> Path:
    body = plistlib.dumps({"ExpirationDate": expires, "ProvisionedDevices": list(udids)})
    path.write_bytes(b"\x30\x82junk" + body + b"\x00trailer")
    return path


class FakeProvisioner:
    def __init__(self, prof_path, lifetime):
        self.prof_path = prof_path
        self.lifetime = lifetime
        self.calls = 0

    def credentials_for(self, udid, name):
        self.calls += 1
        make_profile(self.prof_path, datetime.now(timezone.utc) + self.lifetime)
        return Credentials(Path("x.p12"), "pw", self.prof_path)


class FakeBackend:
    def __init__(self, connected):
        self.connected = set(connected)
        self.installed = []

    def connected_udids(self):
        return self.connected

    def install(self, udid, ipa):
        self.installed.append(udid)


def fake_signer(src, dst, creds):
    dst.write_bytes(b"signed")
    return dst


def build(tmp_path, connected=("UDID1",), lifetime=timedelta(days=7)):
    prov = FakeProvisioner(tmp_path / "p.mobileprovision", lifetime)
    backend = FakeBackend(connected)
    store = Store(tmp_path / "state.json")
    ipas = tmp_path / "ipas"
    ipas.mkdir()
    kit = Ipakit(prov, backend, store, signer=fake_signer, ipa_dir=ipas)
    src = tmp_path / "App.ipa"
    src.write_bytes(b"unsigned")
    return kit, backend, store, src


def test_profile_expiration(tmp_path):
    exp = datetime(2030, 1, 1, tzinfo=timezone.utc)
    p = make_profile(tmp_path / "a.mobileprovision", exp)
    assert profile.expiration(p) == exp
    assert profile.provisioned_udids(p) == ["UDID1"]


def test_install_records_expiry(tmp_path):
    kit, backend, store, src = build(tmp_path)
    app = kit.install(src, "UDID1")
    assert backend.installed == ["UDID1"]
    assert store.apps[0].name == "App"
    assert app.expiry() > datetime.now(timezone.utc) + timedelta(days=6)


def test_not_renewed_when_fresh(tmp_path):
    kit, backend, _s, src = build(tmp_path)
    kit.install(src, "UDID1")
    backend.installed.clear()
    assert kit.renew_due() == []
    assert backend.installed == []


def test_renewed_when_near_expiry(tmp_path):
    kit, backend, store, src = build(tmp_path, lifetime=timedelta(days=1))
    kit.install(src, "UDID1")
    backend.installed.clear()
    kit.provisioner.lifetime = timedelta(days=7)
    assert kit.renew_due() == ["App"]
    assert backend.installed == ["UDID1"]
    assert store.apps[0].expiry() > datetime.now(timezone.utc) + timedelta(days=6)


def test_skipped_when_device_unreachable(tmp_path):
    kit, backend, _s, src = build(tmp_path, lifetime=timedelta(days=1))
    kit.install(src, "UDID1")
    backend.installed.clear()
    backend.connected = set()
    assert kit.renew_due() == []
    assert backend.installed == []


def test_state_persists(tmp_path):
    kit, _b, store, src = build(tmp_path)
    kit.install(src, "UDID1")
    assert len(Store(store.path).apps) == 1


def test_external_engine_renews(tmp_path):
    import sys
    from ipakit.provisioner import ExternalEngine

    marker = tmp_path / "ran.txt"
    code = "import sys; open(sys.argv[1],'a').write(sys.argv[2]+sys.argv[3]+'\\n')"
    engine = ExternalEngine([sys.executable, "-c", code, str(marker), "{udid}", "{ipa}"],
                            timedelta(days=1))
    backend = FakeBackend(["UDID1"])
    store = Store(tmp_path / "state.json")
    ipas = tmp_path / "ipas"
    ipas.mkdir()
    kit = Ipakit(engine, backend, store, ipa_dir=ipas)
    src = tmp_path / "App.ipa"
    src.write_bytes(b"x")
    kit.install(src, "UDID1")
    assert backend.installed == []          # engine installs by itself
    assert marker.read_text().startswith("UDID1")
    assert kit.renew_due() == ["App"]       # 1-day validity is inside the 2-day margin
    assert len(marker.read_text().splitlines()) == 2


def test_external_engine_failure(tmp_path):
    import sys
    import pytest
    from ipakit.provisioner import ExternalEngine

    engine = ExternalEngine([sys.executable, "-c", "import sys; sys.exit(3)"])
    with pytest.raises(RuntimeError):
        engine.sign_and_install(tmp_path / "a.ipa", "U")
