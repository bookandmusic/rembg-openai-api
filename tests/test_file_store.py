import time

from app.file_store import FileStore


def test_put_get():
    store = FileStore(ttl_seconds=60)
    fid = store.put(b"png-data")
    got = store.get(fid)
    assert got == (b"png-data", "image/png")


def test_missing():
    store = FileStore(ttl_seconds=60)
    assert store.get("nope") is None


def test_ttl_expires():
    store = FileStore(ttl_seconds=0)
    fid = store.put(b"x")
    time.sleep(0.01)
    assert store.get(fid) is None


def test_max_items_evicts_oldest():
    store = FileStore(ttl_seconds=3600, max_items=2)
    a = store.put(b"a")
    b = store.put(b"b")
    c = store.put(b"c")
    assert store.get(a) is None
    assert store.get(b) is not None
    assert store.get(c) is not None


def test_max_bytes_evicts():
    store = FileStore(ttl_seconds=3600, max_bytes=10)
    a = store.put(b"12345")
    b = store.put(b"67890")
    # both 5 bytes; adding another 5 forces eviction of oldest
    c = store.put(b"xxxxx")
    assert store.get(a) is None
    assert store.get(b) is not None or store.get(c) is not None
    assert store.get(c) is not None
