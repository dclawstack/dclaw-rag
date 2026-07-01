import fnmatch

from scripts.backup import export_data, import_data


class FakeRedis:
    """Minimal Redis supporting the string/set ops the backup tool uses."""

    def __init__(self):
        self.strings = {}
        self.sets = {}

    def set(self, key, value):
        self.strings[key] = value
        self.sets.pop(key, None)

    def get(self, key):
        return self.strings.get(key)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)
        self.strings.pop(key, None)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def type(self, key):
        if key in self.strings:
            return "string"
        if key in self.sets:
            return "set"
        return "none"

    def scan_iter(self, match):
        keys = list(self.strings) + list(self.sets)
        return [k for k in keys if fnmatch.fnmatch(k, match)]


def _seed(r):
    r.set("user:1", '{"id":"1","email":"a@b.com"}')
    r.set("user:email:a@b.com", "1")
    r.set("collection:c1", '{"id":"c1","tenant_id":"t1"}')
    r.sadd("collections:index", "c1")
    r.set("doc:d1", '{"id":"d1","status":"ready"}')
    r.sadd("docs:t:t1", "d1")
    r.set("apikey:hash", '{"tenant_id":"t1"}')
    # transient — must NOT be backed up
    r.set("rl:t1:123", "5")


def test_export_excludes_transient_keys():
    r = FakeRedis()
    _seed(r)
    data = export_data(r)
    assert "user:1" in data
    assert "collections:index" in data
    assert data["collections:index"]["type"] == "set"
    assert not any(k.startswith("rl:") for k in data)  # rate-limit counters excluded


def test_backup_restore_round_trip():
    src = FakeRedis()
    _seed(src)
    snapshot = export_data(src)

    dst = FakeRedis()
    n = import_data(dst, snapshot)

    assert n == len(snapshot)
    assert export_data(dst) == snapshot  # identical after restore
    assert dst.get("user:1") == '{"id":"1","email":"a@b.com"}'
    assert dst.smembers("docs:t:t1") == {"d1"}
