const { chromium } = require('playwright');
const fs = require('fs');
const CK = JSON.parse(fs.readFileSync('/tmp/wr_cookies3.json','utf8')).map(c=>({name:c.name,value:c.value,domain:c.domain,path:'/'}));
(async () => {
  const b = await chromium.launch({ channel:'chrome', headless:true });
  const ctx = await b.newContext({ userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36', viewport:{width:1440,height:900}, locale:'zh-CN' });
  await ctx.addCookies(CK);
  const p = await ctx.newPage();
  await p.goto('https://weread.qq.com/web/shelf', { waitUntil:'domcontentloaded', timeout:45000 });
  await p.waitForTimeout(4000);
  const all = await ctx.cookies();
  fs.writeFileSync('/tmp/wr_cookies_live.json', JSON.stringify(all.map(c=>({name:c.name,value:c.value,domain:c.domain,path:c.path,secure:c.secure,httpOnly:c.httpOnly})), null, 0));
  console.log('cookies', all.length, all.map(c=>c.name).join(','));
  // 顺便用页面内 fetch 验证
  const r = await p.evaluate(async () => {
    const res = await fetch('/web/shelf/sync', {headers:{'Accept':'application/json'}});
    const j = await res.json();
    return j.bookCount || j.errMsg;
  });
  console.log('in-page shelf:', r);
  await b.close();
})();
