import { beforeEach, describe, expect, it, vi } from "vitest";

import { getToken, login, refreshAccessToken, register } from "./auth";

function mockFetch(opts: { ok?: boolean; status?: number; body?: unknown }) {
  return vi.fn().mockResolvedValue({
    ok: opts.ok ?? true,
    status: opts.status ?? 200,
    json: async () => opts.body ?? {},
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("auth lib", () => {
  it("login stores access + refresh tokens", async () => {
    vi.stubGlobal("fetch", mockFetch({ body: { access_token: "acc", refresh_token: "ref" } }));
    await login("a@b.com", "password1");
    expect(getToken()).toBe("acc");
    expect(localStorage.getItem("dclaw_refresh")).toBe("ref");
  });

  it("register stores tokens too", async () => {
    vi.stubGlobal("fetch", mockFetch({ body: { access_token: "a2", refresh_token: "r2" } }));
    await register("a@b.com", "password1");
    expect(getToken()).toBe("a2");
  });

  it("login surfaces the server error detail", async () => {
    vi.stubGlobal("fetch", mockFetch({ ok: false, status: 401, body: { detail: "bad creds" } }));
    await expect(login("a@b.com", "x")).rejects.toThrow("bad creds");
  });

  it("refreshAccessToken swaps in the new tokens", async () => {
    localStorage.setItem("dclaw_refresh", "old");
    vi.stubGlobal("fetch", mockFetch({ body: { access_token: "new-acc", refresh_token: "new-ref" } }));
    expect(await refreshAccessToken()).toBe(true);
    expect(getToken()).toBe("new-acc");
    expect(localStorage.getItem("dclaw_refresh")).toBe("new-ref");
  });

  it("refreshAccessToken returns false with no refresh token", async () => {
    expect(await refreshAccessToken()).toBe(false);
  });

  it("refreshAccessToken clears tokens when the server rejects", async () => {
    localStorage.setItem("dclaw_token", "a");
    localStorage.setItem("dclaw_refresh", "r");
    vi.stubGlobal("fetch", mockFetch({ ok: false, status: 401 }));
    expect(await refreshAccessToken()).toBe(false);
    expect(getToken()).toBeNull();
  });
});
