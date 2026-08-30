#!/usr/bin/env node
// ima_cos_upload.js —— 把 create_media 返回的 STS 凭证 + 本地文件直传到 COS（ima 入库前置步骤）。
// 用法:
//   node ima_cos_upload.js <credsJsonPath>
//   credsJson 可为 {"items":[{media_id,file_name,file_path,content_type,cos_credential:{...}}]} 或纯数组
//   cos_credential 需含 secret_id / secret_key / token / bucket_name / region / cos_key
// 前置: 在托管 node 工作区安装 SDK -> npm install cos-nodejs-sdk-v5
const fs = require('fs');
const path = require('path');

function loadCOS() {
  const candidates = [
    process.env.NODE_PATH && path.join(process.env.NODE_PATH, 'cos-nodejs-sdk-v5'),
    '/Users/zhy/.workbuddy/binaries/node/workspace/node_modules/cos-nodejs-sdk-v5',
    path.join(__dirname, '..', 'node_modules', 'cos-nodejs-sdk-v5'),
    'cos-nodejs-sdk-v5',
  ].filter(Boolean);
  for (const c of candidates) {
    try { return require(c); } catch (e) { /* try next */ }
  }
  console.error('找不到 cos-nodejs-sdk-v5，请先在托管 node 工作区执行: npm install cos-nodejs-sdk-v5');
  process.exit(2);
}
const COS = loadCOS();

const p = process.argv[2];
if (!p) { console.error('用法: node ima_cos_upload.js <credsJsonPath>'); process.exit(1); }
const data = JSON.parse(fs.readFileSync(p, 'utf8'));
const items = Array.isArray(data) ? data : (data.items || []);

function uploadOne(it) {
  return new Promise((res) => {
    const c = it.cos_credential;
    const cos = new COS({
      SecretId: c.secret_id,
      SecretKey: c.secret_key,
      XCosSecurityToken: c.token,
      FileParallelLimit: 1,
      ChunkParallelLimit: 1,
    });
    let body;
    try { body = fs.readFileSync(it.file_path); }
    catch (e) { console.log('READ_FAIL ' + it.file_name + ' ' + e.message); return res(); }
    cos.putObject(
      { Bucket: c.bucket_name, Region: c.region, Key: c.cos_key, Body: body, ContentType: it.content_type },
      (err) => {
        if (err) console.log('FAIL ' + it.file_name + ' ' + ((err.error && err.error.Message) || err.message));
        else console.log('OK ' + it.file_name + ' media_id=' + it.media_id);
        res();
      }
    );
  });
}

(async () => {
  let ok = 0, fail = 0;
  for (const it of items) {
    process.stderr.write('uploading ' + it.file_name + ' ... ');
    await uploadOne(it);
    process.stderr.write('\n');
  }
  console.log('\n==== DONE: ' + items.length + ' files ====');
})();
