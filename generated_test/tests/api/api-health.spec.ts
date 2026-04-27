import { test, expect } from '@playwright/test';
import { ApiHelper } from '../../utils/api-helper';

test.describe('health', () => {

    test('GET /api/health - returns healthy status', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.get('/api/health');

        expect(response.status()).toBe(200);

        const body = await response.json();
        expect(body).toHaveProperty('status');
        expect(body).toHaveProperty('message');
        expect(body.status).toBe('healthy');
        expect(typeof body.message).toBe('string');
        expect(body.message.length).toBeGreaterThan(0);
    });

    test('GET /api/health - response time is acceptable', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const start = Date.now();
        const response = await apiHelper.get('/api/health');
        const duration = Date.now() - start;

        expect(response.status()).toBe(200);
        expect(duration).toBeLessThan(3000);
    });

    test('GET /api/health - returns correct content-type', async ({ request }) => {
        const apiHelper = new ApiHelper(request);
        const response = await apiHelper.get('/api/health');

        expect(response.status()).toBe(200);
        expect(response.headers()['content-type']).toContain('application/json');
    });
});
