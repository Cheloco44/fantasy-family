import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync, readdirSync} from 'node:fs';
const data=JSON.parse(readFileSync('src/data/clubhouse.json','utf8'));
test('launch includes exactly the eight explicitly labeled portraits',()=>{
 assert.equal(data.managers.length,8);
 for(const m of data.managers){
  assert.equal(m.approved,true);
  assert.equal(m.image,`avatars/${m.slug}.webp`);
  assert.ok(existsSync(`public/${m.image}`));
 }
 assert.equal(readdirSync('public/avatars').length,8);
});
test('Pages deployment is manual, least privilege and cannot access ESPN secrets',()=>{
 const p='.github/workflows/deploy-pages.yml';
 assert.ok(existsSync(p),'Pages workflow must exist');
 const text=readFileSync(p,'utf8');
 for(const marker of ['workflow_dispatch:', 'needs: build', 'pages: write', 'id-token: write', 'persist-credentials: false', 'path: dist', 'BASE_PATH: /fantasy-family/', "github.ref == 'refs/heads/main'"]) assert.ok(text.includes(marker),marker);
 for(const marker of ['secrets.', 'ESPN_S2', 'ESPN_SWID', 'schedule:', 'pull_request_target:', 'contents: write']) assert.ok(!text.includes(marker),marker);
 const uses=[...text.matchAll(/uses:\s*[^@\s]+@([^\s]+)/g)].map(m=>m[1]);
 assert.equal(uses.length,4);
 assert.ok(uses.every(ref=>/^[a-f0-9]{40}$/.test(ref)));
});
