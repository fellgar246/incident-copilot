import { expect, test } from "@playwright/test";

test("demo walks alarm to resolved and keeps status consistent", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/incidents/");
  await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();

  const empty = page.getByRole("heading", { name: "No incidents yet" });
  if (await empty.isVisible().catch(() => false)) {
    await expect(empty).toBeVisible();
  }

  await page.getByTestId("run-simulation").first().click();
  await expect(page.getByTestId("lifecycle")).toBeVisible();
  await expect(page.getByText("DETECTED").first()).toBeVisible();

  await page.getByTestId("investigate").click();
  await expect(page.getByRole("tab", { name: "AI Investigation" })).toBeVisible();
  await page.getByRole("tab", { name: "AI Investigation" }).click();
  await expect(page.getByText("query_logs")).toBeVisible();
  await page.getByRole("tab", { name: "Retrieved Knowledge" }).click();
  await expect(page.getByText(/rb_|source/i).first()).toBeVisible();

  await page.getByTestId("execute-early").click();
  await expect(page.getByTestId("denied-banner")).toBeVisible();
  await expect(page.getByTestId("denied-event")).toBeVisible();

  await page.getByTestId("open-approve").click();
  await expect(page.getByTestId("approval-dialog")).toBeVisible();
  await page.getByTestId("confirm-approve").click();
  await expect(page.getByText("APPROVED").first()).toBeVisible();

  await page.getByTestId("execute").click();
  await expect(page.getByText("RESOLVED").first()).toBeVisible();

  await page.getByRole("tab", { name: "Cost" }).click();
  await expect(page.getByText("Estimated USD")).toBeVisible();
  await page.getByRole("tab", { name: "Trace" }).click();
  await expect(page.locator("dt", { hasText: "agent_run_id" })).toBeVisible();

  const incidentUrl = page.url();
  await page.goto("/evaluations/");
  await expect(page.getByTestId("eval-kpis")).toBeVisible();
  await page.goto("/settings/costs/");
  await expect(page.getByText("Limits cannot be raised from this session.")).toBeVisible();
  await expect(page.getByRole("button", { name: /save|increase/i })).toHaveCount(0);

  await page.goto(incidentUrl);
  await expect(page.getByText("RESOLVED").first()).toBeVisible();
});
