import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import Principal, get_principal, get_rate_limiter
from app.api.main import app

TEST_TENANT = "test-tenant"


class _AllowAllLimiter:
    def check(self, key, limit=None):
        return True, 0


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _auth_and_cleanup():
    # Authenticate every test as a default tenant and neutralize rate limiting
    # (no Redis in CI); the auth- and security-specific tests override these.
    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id=TEST_TENANT)
    app.dependency_overrides[get_rate_limiter] = lambda: _AllowAllLimiter()
    yield
    app.dependency_overrides.clear()
