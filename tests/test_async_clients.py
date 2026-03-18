import asyncio

from lovensepy import Actions, AsyncLANClient
from lovensepy.standard import async_lan as async_lan_module
from lovensepy.transport import async_http as async_http_module
from lovensepy.transport.async_http import AsyncHttpTransport


def test_async_lan_context_manager_closes_transport():
    async def _runner():
        client = AsyncLANClient("TestBot", "127.0.0.1", port=20011)
        closed = {"called": False}

        async def fake_aclose():
            closed["called"] = True

        client._transport.aclose = fake_aclose  # type: ignore[method-assign]

        async with client:
            pass

        assert closed["called"] is True

    asyncio.run(_runner())


def test_async_lan_method_timeout_override_propagates():
    async def _runner():
        client = AsyncLANClient("TestBot", "127.0.0.1", port=20011, timeout=9.0)
        seen_timeout: list[float | None] = []

        async def fake_send_command(payload, timeout=None):  # type: ignore[no-untyped-def]
            seen_timeout.append(timeout)
            return {"code": 200, "type": "OK"}

        client.send_command = fake_send_command  # type: ignore[method-assign]

        await client.function_request({Actions.VIBRATE: 5}, timeout=1.5)
        assert seen_timeout[-1] == 1.5

        await client.function_request({Actions.VIBRATE: 5})
        assert seen_timeout[-1] is None

    asyncio.run(_runner())


def test_async_lan_fingerprint_verification_is_serialized(monkeypatch):
    async def _runner():
        client = AsyncLANClient(
            "TestBot",
            "127.0.0.1",
            use_https=True,
            verify_ssl=False,
        )
        calls = {"count": 0}

        def fake_verify(host, port, fingerprint, timeout):  # type: ignore[no-untyped-def]
            calls["count"] += 1
            # Sleep to make races likely if lock is missing.
            import time

            time.sleep(0.03)
            return True

        monkeypatch.setattr(async_lan_module, "verify_cert_fingerprint", fake_verify)

        results = await asyncio.gather(*(client._ensure_fingerprint_verified() for _ in range(10)))
        assert all(results)
        assert calls["count"] == 1

    asyncio.run(_runner())


def test_async_http_transport_reuses_clients_and_closes(monkeypatch):
    async def _runner():
        class FakeAsyncClient:
            def __init__(self, verify, timeout):  # type: ignore[no-untyped-def]
                self.verify = verify
                self.timeout = timeout
                self.closed = False

            async def aclose(self):
                self.closed = True

        monkeypatch.setattr(async_http_module.httpx, "AsyncClient", FakeAsyncClient)

        transport = AsyncHttpTransport("http://127.0.0.1:20011/command", timeout=2.0)
        client_a = transport._get_client(True)
        client_b = transport._get_client(True)
        client_c = transport._get_client(False)

        assert client_a is client_b
        assert client_a is not client_c
        assert len(transport._clients) == 2

        await transport.aclose()
        assert transport._clients == {}

    asyncio.run(_runner())
