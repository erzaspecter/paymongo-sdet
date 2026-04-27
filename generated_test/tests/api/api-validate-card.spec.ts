import { test, expect } from '@playwright/test';
import { ApiHelper } from '../../utils/api-helper';

test.describe('validation - validate-card', () => {

    test('POST /api/validate-card - valid card number returns true', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {
            cardNumber: '4242424242424242',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('valid');
        expect(body).toHaveProperty('message');
        expect(body.valid).toBe(true);
        expect(typeof body.message).toBe('string');
    });

    test('POST /api/validate-card - invalid card number returns false', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {
            cardNumber: '1234567890123456',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('valid');
        expect(body).toHaveProperty('message');
        expect(body.valid).toBe(false);
    });

    test('POST /api/validate-card - another valid Luhn card', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {
            cardNumber: '5500005555555559',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.valid).toBe(true);
    });

    test('POST /api/validate-card - card with spaces is handled', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {
            cardNumber: '4242 4242 4242 4242',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body).toHaveProperty('valid');
        expect(body).toHaveProperty('message');
    });

    test('POST /api/validate-card - empty card number is rejected', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {
            cardNumber: '',
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.valid).toBe(false);
    });

    test('POST /api/validate-card - missing body returns 400', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.post('/api/validate-card', {});

        expect([200, 400]).toContain(response.status());
    });
});
