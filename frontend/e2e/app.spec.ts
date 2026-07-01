import { expect, test } from "@playwright/test";

async function registerFresh(page: import("@playwright/test").Page, suffix = "") {
  const email = `e2e_${Date.now()}${suffix}@example.com`;
  await page.goto("/login");
  await page.click("text=No account? Create one");
  await page.fill("#email", email);
  await page.fill("#password", "hunter2pass");
  await page.click('button:has-text("Create account")');
  await expect(page).toHaveURL("http://localhost:3003/");
  return email;
}

test("unauthenticated visit is redirected to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});

test("register -> dashboard -> reload stays authed -> logout", async ({ page }) => {
  await registerFresh(page);
  await expect(page.getByText("System Status")).toBeVisible(); // dashboard rendered

  await page.reload();
  await expect(page).toHaveURL("http://localhost:3003/"); // still authed

  await page.click("text=Log out");
  await expect(page).toHaveURL(/\/login$/);
});

test("text ingestion is processed to ready", async ({ page }) => {
  await registerFresh(page, "_ingest");

  await page.goto("/ingest");
  await page.getByRole("tab", { name: /Raw Text/ }).click();
  await page
    .locator("textarea")
    .first()
    .fill("Photosynthesis converts light into chemical energy. ".repeat(20));
  await page.getByRole("button", { name: /Ingest Text/ }).click();

  await expect(page.getByText("Recent uploads")).toBeVisible();
  // the worker embeds + upserts, then the badge flips (models load on first task)
  await expect(page.getByText(/Ready ·/)).toBeVisible({ timeout: 90_000 });
});
