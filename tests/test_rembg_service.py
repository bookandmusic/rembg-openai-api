from unittest.mock import MagicMock, patch

from app.rembg_service import RembgService


def test_session_reuse():
    svc = RembgService(max_sessions=2)
    with patch("app.rembg_service.new_session") as ns:
        ns.side_effect = lambda m: f"session-{m}"
        a1 = svc.get_session("a")
        a2 = svc.get_session("a")
        assert a1 is a2
        assert ns.call_count == 1


def test_lru_evicts_oldest():
    svc = RembgService(max_sessions=2)
    with patch("app.rembg_service.new_session") as ns:
        ns.side_effect = lambda m: f"session-{m}"
        svc.get_session("a")
        svc.get_session("b")
        svc.get_session("c")  # evicts a
        assert "a" not in svc._sessions
        assert list(svc._sessions.keys()) == ["b", "c"]
        svc.get_session("b")  # touch b
        svc.get_session("d")  # evicts c
        assert "c" not in svc._sessions
        assert list(svc._sessions.keys()) == ["b", "d"]


def test_remove_passes_session_and_extra():
    svc = RembgService(max_sessions=1)
    fake_session = MagicMock()
    with (
        patch("app.rembg_service.new_session", return_value=fake_session) as ns,
        patch("app.rembg_service.remove", return_value=b"png-out") as rm,
    ):
        out = svc.remove(b"img", "u2netp", only_mask=True)
        assert out == b"png-out"
        ns.assert_called_once_with("u2netp")
        rm.assert_called_once_with(b"img", session=fake_session, only_mask=True)
