import { Buffer } from 'node:buffer';
import { test, expect } from '@playwright/test';

const API = 'http://127.0.0.1:8765';

test.beforeEach(async ({ request }) => {
  await request.post(`${API}/__reset`);
});

test('upload PDF -> job graph_running -> done -> hỏi đáp có nguồn kèm số trang', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Bắt đầu phiên học/ }).click();
  await expect(page.getByTestId('backend-status')).toContainText('hoạt động');
  await expect(page.getByText('Chưa có tệp nào').first()).toBeVisible();

  await page.getByTestId('pdf-input').setInputFiles({
    name: 'giao-trinh.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 nho'),
  });
  await page.getByRole('button', { name: 'Nạp tài liệu' }).click();

  await expect(page.getByTestId('file-list')).toContainText('giao-trinh.pdf');
  await expect(page.getByTestId('job-row')).toHaveAttribute('data-status', 'graph_running');
  await expect(page.getByTestId('graph-status')).toContainText('đang dựng');
  await expect(page.getByTestId('job-row')).toHaveAttribute('data-status', 'done', { timeout: 15000 });
  await expect(page.getByTestId('graph-status')).toContainText('sẵn sàng');

  await page.getByLabel('Câu hỏi').fill('Gradient descent là gì?');
  await page.getByLabel('Câu hỏi').press('Enter');
  await expect(page.getByText('Gradient descent cập nhật tham số')).toBeVisible();
  await page.getByRole('button', { name: /nguồn trích dẫn/ }).click();
  await expect(page.getByTestId('sources-list')).toContainText('giao-trinh.pdf · trang 3');
  await expect(page.getByTestId('sources-list')).toContainText('0.812');

  // L7: bảng markdown thành <table>; TTS có thanh phát và KHÔNG tự phát.
  await expect(page.locator('table td', { hasText: 'tốc độ học' })).toBeVisible();
  const audio = page.locator('audio[controls]');
  await expect(audio).toHaveCount(1);
  expect(await audio.evaluate((a) => a.paused)).toBe(true);

  // T3: job ở trạng thái cuối xoá được.
  await page.getByRole('button', { name: /Xoá tác vụ giao-trinh\.pdf/ }).click();
  await expect(page.getByTestId('job-row')).toHaveCount(0);
});
