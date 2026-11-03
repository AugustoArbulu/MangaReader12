// Offline contract and safety tests for experimental WeebCentral EN.
// No requests to the live WeebCentral website are performed.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const vm = require('node:vm');
const path = require('node:path');

const script = fs.readFileSync(path.join(__dirname, '../fixtures/keiyoushi-weebcentral-en.js'), 'utf8');
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname,
  '../fixtures/weebcentral-pilot-repository.json'), 'utf8'));
assert.equal(catalog.sources.length, 1, 'isolated pilot must contain one source');
const candidate = catalog.sources[0];
assert.equal(candidate.id, 'kei.weebcentral.en');
assert.equal(candidate.version, '0.1.0');
assert.deepEqual(candidate.domains, ['weebcentral.com']);
assert.equal(candidate.script,
  'https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/keiyoushi-weebcentral-en.js');
assert.equal(crypto.createHash('sha256').update(script, 'utf8').digest('hex'),
  candidate.sha256, 'script and pilot manifest integrity mismatch');
const BASE = 'https://weebcentral.com';
const SERIES = BASE + '/series/series-42/alpha';
const CH1 = BASE + '/chapters/chapter-01';
const CH2 = BASE + '/chapters/chapter-02';
const item = (text='', attrs={}, fields={}) => ({text, attrs, fields});

function runtime(handler) {
  const calls = [];
  const Native = {
    resolveUrl(base, p) { return new URL(p, base).href; },
    httpRequest(raw, cb) {
      const req = JSON.parse(raw);
      calls.push(req);
      let result;
      try { result = handler.http(req.url); }
      catch (e) { throw new Error('Unexpected HTTP request: ' + req.url + ' / ' + e.message); }
      if (typeof result === 'string') result = {body: result};
      cb(JSON.stringify({
        ok: result.ok !== false,
        status: result.status === undefined ? 200 : result.status,
        body: result.body === undefined ? '' : result.body,
        finalURL: result.finalURL || req.url,
        error: result.error
      }));
    },
    htmlSelect(html, raw, cb) {
      const spec = JSON.parse(raw);
      try { cb(JSON.stringify({results: handler.dom(html, spec)})); }
      catch (e) { cb(JSON.stringify({error: String(e.message || e)})); }
    }
  };
  const context = vm.createContext({Native, console});
  new vm.Script(script, {filename: 'keiyoushi-weebcentral-en.js'}).runInContext(context);
  const src = context.source;
  for (const name of ['metadata','popular','search','details','chapters','pages',
                      'browse','browseCategories']) {
    assert.equal(typeof src[name], 'function', name + ' missing');
  }
  function call(method, ...args) {
    return new Promise((resolve, reject) => {
      try {
        const result = src[method](...args, resolve);
        if (result !== undefined) resolve(result);
      } catch (error) { reject(error); }
    });
  }
  return {call, calls};
}
function mock() {
  return runtime({
    http(url) {
      if (url.includes('/search/data?')) return 'LIST';
      if (url.endsWith('/full-chapter-list')) return 'CHAPTERS';
      if (url.endsWith('/images?is_prev=False&reading_style=long_strip')) return 'PAGES';
      if (url === SERIES) return 'DETAILS';
      throw new Error('No fixture for '+url);
    },
    dom(html, spec) {
      if (html === 'LIST') {
        assert(spec.items && spec.next);
        assert.equal(spec.items.selector, 'article > section > a');
        return {
          items: [
            item('', {href: '/series/series-42/alpha'}, {
              title: item('Alpha'),
              source: item('', {srcset: '/covers/alpha-small.jpg 1x, /covers/alpha-big.jpg 2x'})
            }),
            item('', {href: '/series/series-42/alpha'}, {title: item('Duplicate')}),
            item('', {href: 'https://untrusted.example/series/evil/evil'}, {title: item('Reject')}),
            item('', {href: '/series/series-43/beta'}, {
              title: item('Beta'), image: item('', {'data-src': '/covers/beta.png'})
            })
          ], next: [item('Next')]
        };
      }
      if (html === 'DETAILS') {
        assert(spec.title && spec.rows && spec.poster && spec.meta);
        // iOS12-friendly selectors: no CSS :has / :contains or site JS.
        assert(!JSON.stringify(spec).includes(':has'));
        return {
          title: [item('Alpha')],
          rows: [
            item('Author: Pat Example'), item('Artist: Artist A'),
            item('Status: Ongoing'), item('Tag: Fantasy'),
            item('Type: Manhwa'), item('Description: Offline fixture'),
            item('Associated Name: Alpha Alt')
          ],
          poster: [item('', {}, {source:item('',{srcset:'/covers/a.jpg 1x'})})],
          meta: []
        };
      }
      if (html === 'CHAPTERS') {
        assert.equal(spec.chapters.selector, 'div[x-data] > a');
        return {chapters: [
          item('', {href: '/chapters/chapter-02'}, {name: item('Chapter 2'),
            official:item('',{src:'/official-badge.png'})}),
          item('', {href: '/chapters/chapter-01'}, {name: item('Chapter 1')}),
          item('', {href: 'https://evil.example/chapters/1'}, {name:item('Bad')})
        ]};
      }
      if (html === 'PAGES') {
        assert.equal(spec.images.selector, 'section[x-data~=scroll] > img');
        return {images: [
          item('', {src: '/images/page-1.jpg'}),
          item('', {src: 'https://external-cdn.example/forbidden.jpg'}),
          item('', {src: 'https://cdn.weebcentral.com/images/page-2.jpg'})
        ]};
      }
      throw Error('Unsupported mock HTML: '+html);
    }
  });
}
async function main() {
  assert.equal(script.includes('evaluateJavaScript('), false);
  assert.equal(script.includes('document.cookie'), false);
  assert.equal(script.includes('Cloudflare'), false);
  assert.equal(script.includes('access_token'), false);
  const r = mock();
  const meta = await r.call('metadata');
  assert.equal(meta.id, 'kei.weebcentral.en');
  assert.equal(meta.version, '0.1.0');

  const popular = await r.call('popular', 1);
  assert.equal(popular.items.length, 2);
  assert.equal(popular.items[0].id, SERIES);
  assert.equal(popular.items[0].cover, BASE + '/covers/alpha-small.jpg');
  assert.equal(popular.hasNextPage, true);
  assert.match(r.calls[0].url,/sort=Popularity/);
  assert.match(r.calls[0].url,/offset=0/);

  const searched = await r.call('search', 'Alpha', 2, []);
  assert.equal(searched.items.length, 2);
  assert.match(r.calls[1].url,/text=Alpha/);
  assert.match(r.calls[1].url,/sort=Best%20Match/);
  assert.match(r.calls[1].url,/offset=32/);
  assert.equal(r.calls[1].method, 'GET');
  assert.equal(r.calls[1].headers.Accept, 'text/html');

  const cats = await r.call('browseCategories');
  assert.deepEqual(Array.from(cats).map(x=>x.id), ['popular','latest']);
  await r.call('browse','latest',3);
  assert.match(r.calls[2].url,/sort=Latest%20Updates/);
  assert.match(r.calls[2].url,/offset=64/);
  const beforeUnknown = r.calls.length;
  const unknown = await r.call('browse','random',1);
  assert(unknown.__sourceError);
  assert.equal(r.calls.length,beforeUnknown);

  const details = await r.call('details',SERIES);
  assert.equal(details.title,'Alpha');
  assert.equal(details.author,'Pat Example');
  assert.equal(details.artist,'Artist A');
  assert.equal(details.status,'ongoing');
  assert.deepEqual(Array.from(details.genres),['Fantasy','Manhwa']);
  assert.equal(details.cover,BASE+'/covers/a.jpg');
  assert.deepEqual(Array.from(details.altTitles),['Alpha Alt']);

  const chapterList = await r.call('chapters',SERIES);
  assert.equal(chapterList.length,2);
  assert.equal(chapterList[0].id,CH1);
  assert.equal(chapterList[0].number,1);
  assert.equal(chapterList[1].scanlator,'Official');
  assert(r.calls.some(x=>x.url===BASE+'/series/series-42/full-chapter-list'));

  const pages = await r.call('pages',CH1);
  assert.equal(pages.length,2);
  assert.equal(pages[0].index,0);
  assert.equal(pages[1].index,1);
  assert.equal(pages[0].headers.Referer,BASE+'/');
  assert.equal(pages[1].imageUrl,'https://cdn.weebcentral.com/images/page-2.jpg');

  const count = r.calls.length;
  assert((await r.call('details','https://weebcentral.com.evil.example/series/123/x')).__sourceError);
  assert((await r.call('chapters','../unsafe')).__sourceError);
  assert((await r.call('pages','http://weebcentral.com/chapters/1')).__sourceError);
  assert((await r.call('pages','https://weebcentral.com/logout')).__sourceError);
  assert.equal(r.calls.length,count,'invalid paths must not trigger requests');

  const denied = runtime({
    http() { return {status:403,ok:false,body:'DENIED'}; },
    dom() { throw Error('must not parse a blocked response'); }
  });
  assert((await denied.call('popular',1)).__sourceError.includes('403'));
  assert.equal(denied.calls.length,1,'no retries on 403');
  const redirected = runtime({
    http() { return {finalURL:'https://external.example/',body:'irrelevant'}; },
    dom() { throw Error('should not parse cross-site response'); }
  });
  assert((await redirected.call('popular',1)).__sourceError);
  assert.equal(redirected.calls.length,1);

  console.log('PASS WeebCentral offline: 6 API methods, 2 discovery methods, pagination, URLs, typed DTO, CDN fail-closed, HTTP errors');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
