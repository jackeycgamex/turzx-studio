// Render semantic regression checks without a browser, network, or real account.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const sandbox = {window:{}, Intl, Date};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/subscription.js'),'utf8'), sandbox);
const render = sandbox.window.TurzxSubscription.render;
const now = Date.now()/1000;
const source = {status:'live',observed_at:now,stale_seconds:180};
const data = {...source,account:{plan_type:'pro',email:'a•••@example.com'},
  buckets:[{id:'codex',windows:[{remaining_percent:70,duration_minutes:10080,resets_at:now+86400}],credits:{balance:'12.5'}}],reset_count:2,
  chatgpt_feature_limits:{...source,items:[{id:'deep_research',name:'深度研究',remaining:250,resets_at:now+86400},
    {id:'image_gen',name:'图像生成',remaining:1000,resets_at:now+86400}],blocked_features:[]},
  billing:{...source,active:true,will_renew:true,renews_at:Date.parse('2027-01-11T08:00:00Z')/1000,
    expires_at:Date.parse('2027-01-12T08:00:00Z')/1000,purchase_platform:'chatgpt_mobile_android',currency:'USD'}
};
const overview=render(data);
assert.match(overview,/深度研究/);
assert.match(overview,/图像生成/);
assert.match(overview,/1,000<span>次<\/span>/);
assert.match(overview,/Work \/ Codex/);
assert.doesNotMatch(overview,/250<span>%/);
assert.match(render(data,'billing'),/2027\/01\/11/);
assert.doesNotMatch(render(data,'billing'),/2027\/01\/12/);
assert.match(render(data,'billing'),/Google Play/);
assert.match(render(data,'billing'),/实扣金额未提供/);
const cancelled=structuredClone(data); cancelled.billing.will_renew=false;
assert.match(render(cancelled,'billing'),/不再自动续费/);
const partial=structuredClone(data); partial.chatgpt_feature_limits.status='stale';
assert.match(render(partial),/部分来源未同步/);
assert.match(render(partial),/feature-cell old/);
assert.doesNotMatch(render(partial),/shared-cell old/);
const missing=structuredClone(data); missing.chatgpt_feature_limits.items[0].remaining=null;
assert.match(render(missing),/feature-value">—<\/div>/);
const zero=structuredClone(data); zero.chatgpt_feature_limits.items[0].remaining=0;
assert.match(render(zero),/额度已耗尽/);
const malicious=structuredClone(data); malicious.chatgpt_feature_limits.items[0].name='<img src=x onerror=alert(1)>';
assert.match(render(malicious),/&lt;img/);
assert.doesNotMatch(render(malicious),/<img src=x/);
const expired=structuredClone(data); expired.chatgpt_feature_limits.items[0].resets_at=now-1;
assert.match(render(expired,'entitlements'),/等待更新/);
const blocked=structuredClone(data); blocked.chatgpt_feature_limits.blocked_features=['deep_research'];
assert.match(render(blocked,'entitlements'),/当前受限/);
console.log('Subscription UI semantics passed: counters, renewal, stale separation, missing/zero and escaping.');
