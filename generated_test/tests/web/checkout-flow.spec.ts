import { test, expect } from '@playwright/test';

test.describe('Checkout Flow - E2E', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForLoadState('networkidle');
    });

    test('complete checkout flow with valid details', async ({ page }) => {
        // Fill email and trigger validation
        await page.locator('input[name="email"]').click();
        await page.locator('input[name="email"]').fill('maria.santos@example.com');

        // Fill card number and wait for Luhn validation API
        await page.locator('input[name="cardNumber"]').click();
        await page.locator('input[name="cardNumber"]').fill('4242424242424242');

        const [cardResp] = await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/validate-card'), { timeout: 10000 }),
            page.locator('input[name="cardNumber"]').blur(),
        ]);
        expect(cardResp.status()).toBe(200);

        // Wait for green border to confirm card is valid
        await expect(page.locator('input[name="cardNumber"]')).toHaveClass(/border-green-400/, { timeout: 5000 });

        // Fill expiry
        await page.locator('input[name="expiry"]').fill('1226');

        // Fill CVV
        await page.locator('input[name="cvv"]').fill('123');

        // Fill amount
        await page.locator('input[name="amount"]').fill('50');

        // Submit and wait for checkout API
        const [checkoutResp] = await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/checkout'), { timeout: 10000 }),
            page.locator('button[type="submit"]').click(),
        ]);

        expect(checkoutResp.status()).toBe(200);
        const body = await checkoutResp.json();
        expect(body.status).toBe('success');

        // Validate success message visible in UI
        await expect(page.locator('div').filter({ hasText: /Payment processed successfully/i }).first())
            .toBeVisible({ timeout: 10000 });
    });

    test('shows error when submitting with invalid card', async ({ page }) => {
        // Fill email
        await page.locator('input[name="email"]').fill('test@example.com');

        // Fill invalid card and wait for validation
        await page.locator('input[name="cardNumber"]').fill('1234567890123456');

        const [cardResp] = await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/validate-card'), { timeout: 10000 }),
            page.locator('input[name="cardNumber"]').blur(),
        ]);

        const body = await cardResp.json();
        expect(body.valid).toBe(false);

        // Red border confirms invalid card
        await expect(page.locator('input[name="cardNumber"]')).toHaveClass(/border-red-400/, { timeout: 5000 });

        // Fill remaining required fields
        await page.locator('input[name="expiry"]').fill('1226');
        await page.locator('input[name="cvv"]').fill('123');
        await page.locator('input[name="amount"]').fill('50');

        // Submit — should be blocked by card validation
        await page.locator('button[type="submit"]').click();
        await page.waitForTimeout(1000);

        // Error message should appear, no checkout API call made
        await expect(page.locator('div').filter({ hasText: /Please enter a valid card number/i }).first())
            .toBeVisible({ timeout: 5000 });
    });

    test('card validation triggers on blur and shows result', async ({ page }) => {
        await page.locator('input[name="cardNumber"]').fill('4242424242424242');

        const [response] = await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/validate-card'), { timeout: 10000 }),
            page.locator('input[name="cardNumber"]').blur(),
        ]);

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.valid).toBe(true);

        // Green border appears for valid card
        await expect(page.locator('input[name="cardNumber"]')).toHaveClass(/border-green-400/, { timeout: 5000 });
    });

    test('email validation soft-fails gracefully on 500', async ({ page }) => {
        await page.locator('input[name="email"]').fill('user@example.com');

        const [response] = await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/validate-email'), { timeout: 10000 }),
            page.locator('input[name="email"]').blur(),
        ]);

        // API always returns 500 - known bug
        expect(response.status()).toBe(500);

        // Warning shown but user can still proceed (soft fail)
        await expect(page.locator('p').filter({ hasText: /temporarily unavailable|still proceed/i }).first())
            .toBeVisible({ timeout: 5000 });
    });
});
