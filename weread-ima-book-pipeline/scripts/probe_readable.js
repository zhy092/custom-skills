/**
 * 探测一本书是否被「试读结束」挡住：打开阅读器翻 N 页，看页面是否出现付费墙。
 * 用法: node probe_readable.js <hash1> [hash2 ...]
 * 输出: 每行 "hash 可读|试读墙|异常"
 */
const { chromium } = require('playwright');
const fs = require('fs');

const CK = JSON.parse(fs.readFileSync('/tmp/wr_cookies3.json', 'utf8'))
  .map(c => ({ name: c.name, value: c.value, domain: c.domain, path: '/' }));

(async () => {
  const hashes = process.argv.slice(2);
  if (!hashes.length) { console.error('用法: node probe_readable.js <hash...>'); process.exit(1); }
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const ctx = await b.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 900 }, locale: 'zh-CN'
  });
  await ctx.addCookies(CK);
  for (const h of hashes) {
    const p = await ctx.newPage();
    let verdict = '异常';
    try {
      await p.goto('https://weread.qq.com/web/reader/' + h, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForTimeout(4500);
      const N = parseInt(process.env.FLIPS || '60', 10);
      let wall = false;
      for (let i = 0; i < N; i++) {
        await p.keyboard.press('ArrowRight'); await p.waitForTimeout(450);
        if (i % 10 === 9) {
          const tt = await p.evaluate(() => document.body.innerText);
          if (/试读结束|付费会员卡可读/.test(tt)) { wall = true; break; }
        }
      }
      if (wall) { verdict = '试读墙'; } else {
      const t = await p.evaluate(() => document.body.innerText);
      if (/试读结束|付费会员卡可读|购买后阅读/.test(t)) verdict = '试读墙';
      else if (/上一页|下一页/.test(t)) verdict = '可读'; }
    } catch (e) { verdict = '异常'; }
    await p.close();
    console.log(h, verdict);
  }
  await b.close();
})();
