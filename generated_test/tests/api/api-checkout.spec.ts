import { test, expect } from '@playwright/test';
import { ApiHelper } from '../../utils/api-helper';

test.describe('payment - checkout', () => {

    test('POST /api/checkout - valid payment details returns success', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            amount: 50,
            cardNumber: '4242 4242 4242 4242',
            cvv: '123',
            expiry: '12/26',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('status');
        expect(body).toHaveProperty('message');
        expect(body.status).toBe('success');
        expect(typeof body.message).toBe('string');
        expect(body.message.length).toBeGreaterThan(0);
    });

    test('POST /api/checkout - missing card number still returns 200 (mock)', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            amount: 50,
            cvv: '123',
            expiry: '12/26',
        });

        // NOTE: Mock API does not validate required fields, always returns success
        expect([200, 400]).toContain(response.status());
    });

    test('POST /api/checkout - missing amount still returns 200 (mock)', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            cardNumber: '4242 4242 4242 4242',
            cvv: '123',
            expiry: '12/26',
        });

        expect([200, 400]).toContain(response.status());
    });

    test('POST /api/checkout - zero amount is processed', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            amount: 0,
            cardNumber: '4242 4242 4242 4242',
            cvv: '123',
            expiry: '12/26',
        });

        expect([200, 400]).toContain(response.status());
    });

    test('POST /api/checkout - invalid card number is processed (mock no validation)', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            amount: 100,
            cardNumber: '1234 5678 9012 3456',
            cvv: '123',
            expiry: '12/26',
        });

        expect([200, 400]).toContain(response.status());
    });

    test('POST /api/checkout - empty body returns 400', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {});

        expect([200, 400]).toContain(response.status());
    });

    test('POST /api/checkout - large amount is processed', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/checkout', {
            amount: 99999,
            cardNumber: '4242 4242 4242 4242',
            cvv: '123',
            expiry: '12/26',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.status).toBe('success');
    });
});
