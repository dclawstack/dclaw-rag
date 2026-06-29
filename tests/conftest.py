import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import Principal, get_principal
from app.api.main import app

TEST_TENANT = "test-tenant"


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _auth_and_cleanup():
    # Authenticate every test as a default tenant; auth-specific tests override
    # or remove this. Cleared after each test.
    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id=TEST_TENANT)
    yield
    app.dependency_overrides.clear()
