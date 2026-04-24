import { test } from "../fixtures";
import { authStatePath, ensureAuthStateDir, loginThroughUi } from "../helpers/auth";

test("bootstrap authenticated storage state", async ({ page }) => {
  await ensureAuthStateDir();
  await loginThroughUi(page);
  await page.context().storageState({ path: authStatePath });
});
