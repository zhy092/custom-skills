/**
 * 微信读书「加入书架」——用真实浏览器点击，最稳。
 * 用法: node shelf_add.js <bookId|deepLink>
 * 输出: JSON 结果（added: true/false, reason）
 */
const { chromium } = require('playwright');
const fs = require('fs');

const CK = JSON.parse(fs.readFileSync('/tmp/wr_cookies3.json', 'utf8'))
  .map(c => ({ name: c.name, value: c.value, domain: c.domain, path: '/' }));

(async () => {
  const target = process.argv[2];
  if (!target) { console.error('用法: node shelf_add.js <bookId|deepLink>'); process.exit(1); }
  const url = target.startsWith('http') ? target : `https://weread.qq.com/web/reader/${target}`;

  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 900 }, locale: 'zh-CN'
  });
  await ctx.addCookies(CK);
  const page = await ctx.newPage();
  const out = { url, added: false, reason: '' };

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(3500);

    // 已加入的迹象
    const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 4000));
    if (/已在书架|已加入书架|移出书架/.test(bodyText)) {
      out.reason = 'already_on_shelf';
      await browser.close();
      console.log(JSON.stringify(out));
      return;
    }

    // 找「加入书架」按钮
    const btn = page.getByText('加入书架', { exact: false }).first();
    if (await btn.count() === 0) {
      out.reason = 'button_not_found';
      fs.writeFileSync('/tmp/shelf_add_last.html', await page.content());
      await page.screenshot({ path: '/tmp/shelf_add_last.png', fullPage: false });
    } else {
      await btn.click({ timeout: 8000 });
      await page.waitForTimeout(2500);
      out.added = true;
      out.reason = 'clicked';
    }
  } catch (e) {
    out.reason = 'error: ' + String(e).slice(0, 160);
  }
  await browser.close();
  console.log(JSON.stringify(out));
})();
