// Self-contained offline tests for M13-A JS source contract (Node, no site requests).
// The HTML selector bridge is simulated at the Native boundary. It verifies
// DTO shape and URL routing, not live WebKit parsing or site availability.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const vm = require('node:vm');
const path = require('node:path');

// Every installed script must exactly match the SHA-256 pinned in the
// published catalog. Catch mismatches before an on-device update is offered.
function verifyPinnedCatalog() {
  const catalog=JSON.parse(fs.readFileSync(
    path.join(__dirname,'../fixtures/keiyoushi-selected-repository.json'),'utf8'));
  const sources=catalog.sources || [];
  assert.equal(sources.length,3,'Pilot catalog still has three sources');
  for(const source of sources) {
    const expected=source.script.split('/').pop();
    const bytes=fs.readFileSync(path.join(__dirname,'../fixtures',expected));
    const actual=crypto.createHash('sha256').update(bytes).digest('hex');
    assert.equal(actual,source.sha256,'SHA-256 pin mismatch for '+source.id);
    if(source.id==='kei.webtoons.en') {
      assert.equal(source.version,'0.1.7');
    }
  }
  console.log('PASS Keiyoushi catalog script SHA-256 integrity');
}

function node(text='', attrs={}, fields={}) { return {text,attrs,fields}; }
function enc(o) { return JSON.stringify(o).replace(/"/g,'&quot;'); }
function runtime(filename, respond, preserveInvalidAbsoluteURL=false) {
  const calls=[];
  const Native={
    resolveUrl(base,part) {
      // iOS 12 NSURL may reject a literal Unicode, whitespace, or bracket
      // in an absolute URL and the native bridge then returns raw input.
      if(preserveInvalidAbsoluteURL && /^https:\/\//i.test(part))return part;
      return new URL(part,base).href;
    },
    httpRequest(raw,callback) {
      const req=JSON.parse(raw); calls.push(req.url);
      const val=respond.http(req.url);
      callback(JSON.stringify({ok:true,status:200,body:typeof val==='string'?val:JSON.stringify(val),finalURL:req.url}));
    },
    htmlSelect(html,raw,callback) {
      const specs=JSON.parse(raw);
      try {callback(JSON.stringify({results:respond.dom(html,specs)}));}
      catch(e) { callback(JSON.stringify({error:e.message}));}
    }
  };
  const context=vm.createContext({Native,URL,console});
  const file=fs.readFileSync(path.join(__dirname,'../fixtures',filename),'utf8');
  new vm.Script(file,{filename}).runInContext(context);
  const source=context.source;
  assert(source,'source global missing: '+filename);
  for(const key of ['metadata','popular','search','details','chapters','pages']) {
    assert.equal(typeof source[key],'function','method '+key);
  }
  function call(name,...args) {
    return new Promise((resolve,reject)=>{
      try {const value=source[name](...args,resolve); if(value!==undefined) resolve(value);}
      catch(e) {reject(e);}
    });
  }
  return {call,calls};
}
async function testManhwa18() {
  const r=runtime('keiyoushi-manhwa18net.js',{
    http(url) {
      if(url.includes('/manga-list')||url.includes('tim-kiem'))return 'LIST';
      if(url.includes('/manga/a/b')) return 'PAGES';
      if(url.includes('/manga/a'))return 'DETAILS';
      throw Error('unexpected URL '+url);
    },
    dom(html,specs) {
      if(specs.app) {
        const props=html==='LIST'?{paginate:{data:[{slug:'a',name:'A',cover_url:'/a.jpg'}],next_page_url:'/page2'}}:
          html==='DETAILS'?{manga:{slug:'a',name:'A',status_id:0,genres:[{name:'Drama'}]},
            chapters:[{name:'C1',slug:'b',created_at:'2026-01-01T00:00:00Z'}]}:
          {chapterContent:'IMAGES'};
        return {app:[node('',{'data-page':enc({props})})]};
      }
      if(specs.pages)return {pages:[node('',{src:'/1.jpg'}),node('',{'data-src':'/2.jpg'})]};
      throw Error('unexpected DOM '+html);
    }
  });
  assert.equal((await r.call('metadata')).id,'kei.manhwa18net');
  assert.equal((await r.call('popular',1)).items[0].title,'A');
  assert.equal((await r.call('search','a',1,[])).hasNextPage,true);
  const details=await r.call('details','a');assert.equal(details.status,'ongoing');
  const chapters=await r.call('chapters','a');assert.equal(chapters[0].id,'a/b');
  const pages=await r.call('pages','a/b');assert.equal(pages.length,2);
  assert(pages[1].imageUrl.endsWith('/2.jpg'));
  console.log('PASS Manhwa18.net: 6 source methods, Inertia props, chapters, pages');
}
async function testHotcomics() {
  const root='https://hotcomics.io';
  const r=runtime('keiyoushi-hotcomics.js',{
    http(url) {return url.includes('/chapter/')?'PAGES':url.endsWith('/book/a')?'DETAILS':'LIST';},
    dom(html,specs) {
      if(specs.entries && html==='DETAILS')return {entries:[node('',{onclick:"popupLogin('/chapter/1')"},{
        name:node('C1'),date:node('Jan 1, 2026')
      })]};
      if(specs.entries)return {entries:[node('',{href:'/book/a'},{
        title:node('Comic A'),cover:node('',{'data-src':'/cover.jpg'})
      })],next:[]};
      if(specs.body)return {body:[node('',{},{
        title:node('Comic A'),writer:node('ⓒ Author'),
        genre:node('Fantasy / Romance'),status:node('End'),
        intro:node('Intro'),description:node('Longer text')
      })]};
      if(specs.images)return {images:[node('',{'data-src':'/page1.png'})]};
      throw Error('unexpected selector');
    }
  });
  assert.equal((await r.call('metadata')).id,'kei.hotcomics');
  assert.equal((await r.call('popular',1)).items[0].title,'Comic A');
  assert.equal((await r.call('search','comic',1,[])).items.length,1);
  assert.equal((await r.call('details',root+'/book/a')).status,'completed');
  const chapters=await r.call('chapters',root+'/book/a');
  assert(chapters[0].id.endsWith('/chapter/1'));
  const pages=await r.call('pages',root+'/chapter/1');
  assert.equal(pages.length,1);
  console.log('PASS HotComics: 6 source methods, listing/details/chapter/pages');
}
async function testWebtoons() {
  const root='https://www.webtoons.com/en/original/series/list?title_no=42';
  const r=runtime('keiyoushi-webtoons-en.js',{
    http(url) {
      if(url.includes('/api/v1/'))return {result:{episodeList:[{episodeTitle:'Episode 1',viewerLink:'https://www.webtoons.com/en/original/series/viewer?title_no=42&episode_no=1'}]}};
      if(url.includes('viewer?'))return 'PAGES';
      if(url.includes('title_no=42'))return 'DETAILS';
      return 'LIST';
    },
    dom(html,specs) {
      if(specs.items)return {items:[node('',{href:root},{
        title:node('Webtoon A'),cover:node('',{src:'https://webtoon-phinf.pstatic.net/cover.jpg'})
      })],next:[]};
      if(specs.body)return {body:[node('',{},{
        title:node('Webtoon A'),author:node('Creator'),
        description:node('Description'),status:node('EVERY MONDAY')
      })],coverMeta:[node('',{content:'https://webtoon-phinf.pstatic.net/cover.jpg'})]};
      if(specs.images)return {images:[node('',{'data-url':'https://webtoon-phinf.pstatic.net/page1.jpg'})]};
      throw Error('unknown DOM');
    }
  });
  assert.equal((await r.call('metadata')).id,'kei.webtoons.en');
  const initialListing=await r.call('popular',1);
  assert.equal(initialListing.items.length,1);
  assert.equal(initialListing.items[0].cover,'https://swebtoon-phinf.pstatic.net/cover.jpg');
  assert.equal(initialListing.items[0].coverDiagnostic.coverFound,true);
  assert.equal(initialListing.items[0].coverDiagnostic.outputClass,'pstatic-https');
  assert(initialListing.items[0].coverDiagnostic.outputLength>0);
  assert.equal((await r.call('search','a',1,[])).items.length,1);
  assert.equal((await r.call('details',root)).status,'ongoing');
  const chapters=await r.call('chapters',root);
  assert.equal(chapters[0].number,1);
  const pages=await r.call('pages',chapters[0].id);
  assert.equal(pages.length,1);
  // Regression: rankings may render an inert data: placeholder in src and
  // provide the real thumbnail URL in a deferred source attribute.
  const lazy=runtime('keiyoushi-webtoons-en.js',{
    http() {return 'LIST';},
    dom(html,specs) {
      assert(specs.items);
      return {items:[
        node('',{href:root},{title:node('Lazy thumbnail'),
          cover:node('',{src:'data:image/gif;base64,AA==',
            'data-src':'https://webtoon-phinf.pstatic.net/real-cover.jpg?type=q90'})}),
        node('',{href:'https://www.webtoons.com/en/original/another/list?title_no=43'},
          {title:node('Srcset thumbnail'),
          cover:node('',{src:'data:image/svg+xml;base64,AA==',
            srcset:'https://webtoon-phinf.pstatic.net/cover-1.jpg 1x, https://webtoon-phinf.pstatic.net/cover-2.jpg 2x'})})
      ],next:[]};
    }
  });
  const lazyResult=await lazy.call('popular',1);
  assert.equal(lazyResult.items.length,2);
  assert.equal(lazyResult.items[0].cover,'https://swebtoon-phinf.pstatic.net/real-cover.jpg?type=q90');
  assert.equal(lazyResult.items[1].cover,'https://swebtoon-phinf.pstatic.net/cover-1.jpg');
  // Build32 physical report: adjacent list covers returned HTTP200 while a
  // middle card had no HTTPS URL. Cover fallbacks must stay within the card.
  const variants=runtime('keiyoushi-webtoons-en.js',{
    http() {return 'LIST';},
    dom(html,specs) {
      assert(specs.items);
      assert(specs.items.fields.coverHost && specs.items.fields.coverPicture);
      return {items:[
        node('',{href:root},{title:node('Second image lazy'),
          cover:node('',{src:'data:image/gif;base64,AA=='}),
          coverLazy:node('',{'data-src':'//webtoon-phinf.pstatic.net/second.jpg?type=q90'})}),
        node('',{href:'https://www.webtoons.com/en/original/c/list?title_no=43'},
          {title:node('Picture srcset'),
          cover:node('',{src:'data:image/gif;base64,AA=='}),
          coverPicture:node('',{srcset:'https://webtoon-phinf.pstatic.net/picture.jpg 1x'})}),
        node('',{href:'https://www.webtoons.com/en/original/d/list?title_no=44'},
          {title:node('CSS background'),
          coverStyle:node('',{style:'background-image: url("https://webtoon-phinf.pstatic.net/css.jpg?type=q90")'})}),
        node('',{href:'https://www.webtoons.com/en/original/e/list?title_no=45',
          'data-cover':'https://webtoon-phinf.pstatic.net/anchor.jpg'},
          {title:node('Card data cover')}),
        node('',{href:'https://www.webtoons.com/en/original/f/list?title_no=46',
          'data-cover':'http://webtoon-phinf.pstatic.net/unsafe.jpg'},
          {title:node('Unsafe cover'),cover:node('',{src:'https://not-allowed.example/out.jpg'})})
      ],next:[]};
    }
  });
  const variantsResult=await variants.call('popular',1);
  assert.equal(variantsResult.items.length,5);
  assert.equal(variantsResult.items[0].cover,'https://swebtoon-phinf.pstatic.net/second.jpg?type=q90');
  assert.equal(variantsResult.items[1].cover,'https://swebtoon-phinf.pstatic.net/picture.jpg');
  assert.equal(variantsResult.items[2].cover,'https://swebtoon-phinf.pstatic.net/css.jpg?type=q90');
  assert.equal(variantsResult.items[3].cover,'https://swebtoon-phinf.pstatic.net/anchor.jpg');
  assert.equal(variantsResult.items[4].cover,null);
  assert.equal(variantsResult.items[4].coverDiagnostic.coverFound,false);
  assert.equal(variantsResult.items[4].coverDiagnostic.outputClass,'empty');
  assert.equal(variantsResult.items[4].coverDiagnostic.outputLength,0);
  assert(variantsResult.items[4].coverDiagnostic.attributes.includes('card.data-cover'));
  assert.equal(variants.calls.length,1,'cover fallback must not trigger extra HTTP requests');
  const trace=await variants.call('inspectCover',
    'https://www.webtoons.com/en/original/f/list?title_no=46');
  assert.equal(trace.matched,true);
  assert.equal(trace.coverFound,false);
  assert(trace.attributes.includes('card.data-cover'));
  assert(trace.kinds.includes('card.data-cover=http'));
  const missing=await variants.call('inspectCover','https://www.webtoons.com/en/unknown/list?title_no=47');
  assert.equal(missing.matched,false);
  assert.equal(variants.calls.length,1,'diagnostic must not make extra HTTP requests');
  const positive=await variants.call('inspectCover',root);
  assert.equal(positive.coverFound,true);
  assert.equal(positive.outputClass,'pstatic-https');
  assert(positive.kinds.includes('coverLazy.data-src=protocol-relative'));
  // Same series may appear twice in separate ranking pages with different
  // image markup. The first row's observation must survive a later lookup.
  let rankingVisit=0;
  const duplicate=runtime('keiyoushi-webtoons-en.js',{
    http() {rankingVisit++;return 'LIST';},
    dom(html,specs) {
      if(!specs.items)throw Error('unexpected selector');
      return {items:[node('',{href:root},{title:node('Duplicate ranking entry'),
        cover:rankingVisit===1
          ?node('',{src:'https://webtoon-phinf.pstatic.net/valid.jpg'})
          :node('',{src:'data:image/svg+xml;base64,AA=='})})],next:[]};
    }
  });
  const original=(await duplicate.call('popular',1)).items[0];
  assert.equal(original.coverDiagnostic.coverFound,true);
  const duplicateLatest=(await duplicate.call('popular',2)).items[0];
  assert.equal(duplicateLatest.coverDiagnostic.coverFound,false);
  assert.equal(original.coverDiagnostic.coverFound,true,'snapshot of original row must be preserved');
  assert.equal((await duplicate.call('inspectCover',root)).coverFound,false,
    'legacy map by id can be overwritten');
  assert.equal(duplicate.calls.length,2,'snapshot must not trigger extra HTTP');

  // Details diagnostic observes og:image presence using exactly the
  // details() request; absence must not be mistaken for an HTTP image error.
  const noMeta=runtime('keiyoushi-webtoons-en.js',{
    http(){return 'DETAILS';},
    dom(html,specs) {
      assert(specs.coverMeta);
      return {body:[node('',{},{
        title:node('Missing meta'),status:node('COMPLETE')
      })],coverMeta:[]};
    }
  });
  const emptyDetails=await noMeta.call('details',root);
  assert.equal(emptyDetails.cover,null);
  const detailsTrace=await noMeta.call('inspectDetailsCover',root);
  assert.equal(detailsTrace.matched,true);
  assert.equal(detailsTrace.metaPresent,false);
  assert.equal(detailsTrace.contentPresent,false);
  assert.equal(detailsTrace.resolvedFound,false);
  assert.equal(noMeta.calls.length,1,'metadata inspection must not fetch details twice');
  const originalDetailsTrace=await r.call('inspectDetailsCover',root);
  assert.equal(originalDetailsTrace.metaPresent,true);
  assert.equal(originalDetailsTrace.contentClass,'pstatic-https');
  assert.equal(originalDetailsTrace.resolvedFound,true);

  // iOS12 regressions: native NSURL rejects some unescaped literal bytes
  // (unlike the modern WHATWG URL test helper). Normalize permitted image
  // hosts without modifying URL delimiters or double-encoding valid escapes.
  const badImage='https://webtoon-phinf.pstatic.net/Manga [한글].jpg?type=q90&x=a';
  const expectedImage='https://swebtoon-phinf.pstatic.net/Manga%20%5B%ED%95%9C%EA%B8%80%5D.jpg?type=q90&x=a';
  const encodedURL='https://webtoon-phinf.pstatic.net/already%20encoded%2Fpart.jpg?type=q90';
  const unsafeURL='https://webtoon-phinf.pstatic.net/bad%XZ.jpg';
  const unicode=runtime('keiyoushi-webtoons-en.js',{
    http(url){return url.includes('title_no=42')?'DETAILS':'LIST';},
    dom(html,specs){
      if(specs.items)return {items:[
        node('',{href:root},{title:node('Unescaped image'),
          cover:node('',{src:badImage})}),
        node('',{href:'https://www.webtoons.com/en/original/b/list?title_no=43'},
          {title:node('Already encoded'),cover:node('',{src:encodedURL})}),
        node('',{href:'https://www.webtoons.com/en/original/c/list?title_no=44'},
          {title:node('Malformed percent'),cover:node('',{src:unsafeURL})}),
        node('',{href:'https://www.webtoons.com/en/original/d/list?title_no=45'},
          {title:node('Off domain'),cover:node('',{src:'https://other.example/x [bad].jpg'})}),
        node('',{href:'https://www.webtoons.com/en/original/e/list?title_no=46'},
          {title:node('Control characters'),
            cover:node('',{src:'https://webtoon-phinf.pstatic.net/control\n.jpg'})})
      ],next:[]};
      if(specs.body)return {
        body:[node('',{}, {title:node('Unescaped image')})],
        coverMeta:[node('',{content:badImage})]
      };
      throw Error('unexpected selector');
    }
  },true);
  const repaired=await unicode.call('popular',1);
  assert.equal(repaired.items[0].cover,expectedImage);
  assert.equal(repaired.items[0].coverDiagnostic.outputClass,'pstatic-https');
  assert.equal(repaired.items[1].cover,
    'https://swebtoon-phinf.pstatic.net/already%20encoded%2Fpart.jpg?type=q90');
  assert.equal(repaired.items[2].cover,null);
  assert.equal(repaired.items[3].cover,null);
  assert.equal(repaired.items[4].cover,null);
  const repairedDetails=await unicode.call('details',root);
  assert.equal(repairedDetails.cover,expectedImage);
  assert.equal((await unicode.call('inspectDetailsCover',root)).resolvedFound,true);
  assert.equal(unicode.calls.length,2,'URL normalization must not add HTTP requests');
  console.log('PASS Webtoons EN: strict iOS12 image URL encoding, existing percent escapes and domain guard');

  // Regression: Webtoons episode `data-url` images must receive the same
  // legacy-safe encoding as covers, without rewriting the chapter image CDN
  // to the alternate thumbnail host or triggering additional requests.
  const chapterURL='https://www.webtoons.com/en/original/series/viewer?title_no=42&episode_no=1';
  const chapterMedia='https://webtoon-phinf.pstatic.net/Panel [한글].jpg?type=q90&x=1';
  const chapterFixture=runtime('keiyoushi-webtoons-en.js',{
    http(url){assert.equal(url,chapterURL);return 'PAGES';},
    dom(html,specs){
      assert(specs.images,'single expected chapter DOM selection');
      return {images:[
        node('',{'data-url':chapterMedia}),
        node('',{'data-url':'https://webtoon-phinf.pstatic.net/encoded%20panel.png?x=%2F'}),
        node('',{'data-url':'//webtoon-phinf.pstatic.net/relative-protocol.jpg'}),
        node('',{'data-url':'/en/images/same-origin.jpg'}),
        node('',{'data-url':'https://other.example/forbidden.jpg'}),
        node('',{'data-url':'https://webtoon-phinf.pstatic.net/bad%GG.jpg'}),
        node('',{'data-url':'https://webtoon-phinf.pstatic.net/control\n.jpg'})
      ]};
    }
  },true);
  const chapterPages=await chapterFixture.call('pages',chapterURL);
  assert.equal(chapterPages.length,4,'unsafe URLs must be dropped, preserving valid sequence');
  assert.equal(chapterPages[0].imageUrl,
    'https://webtoon-phinf.pstatic.net/Panel%20%5B%ED%95%9C%EA%B8%80%5D.jpg?type=q90&x=1');
  assert.equal(chapterPages[1].imageUrl,
    'https://webtoon-phinf.pstatic.net/encoded%20panel.png?x=%2F');
  assert.equal(chapterPages[2].imageUrl,'https://webtoon-phinf.pstatic.net/relative-protocol.jpg');
  assert.equal(chapterPages[3].imageUrl,'https://www.webtoons.com/en/images/same-origin.jpg');
  assert.deepEqual(chapterPages.map(p=>p.index),[0,1,2,3]);
  assert(chapterPages.every(p=>p.headers.Referer==='https://www.webtoons.com/'));
  assert.equal(chapterFixture.calls.length,1,'no per-image probe or extra chapter request');
  console.log('PASS Webtoons EN: iOS12-safe chapter page URLs, unchanged CDN host and order');

  console.log('PASS Webtoons EN: exact row snapshots survive duplicate ranking and details meta check');
  console.log('PASS Webtoons EN: same-card lazy/picture/background fallbacks and unsafe URL rejection');
  console.log('PASS Webtoons EN: list cover URLs normalized to permitted image CDN');
  console.log('PASS Webtoons EN: 6 source methods, chapter JSON/pages');
}
async function testSecurity() {
  const r=runtime('keiyoushi-hotcomics.js',{http(){throw Error('unsafe request')},dom(){throw Error('unsafe DOM')}});
  const res=await r.call('pages','http://hotcomics.io/chapter/1');
  assert(res.__sourceError,'cleartext chapter must fail');
  const x=runtime('keiyoushi-manhwa18net.js',{http(){throw Error('unneeded request')},dom(){throw Error('unneeded DOM')}});
  const bad=await x.call('pages','too/many/path/pieces');
  assert(bad.__sourceError,'invalid chapter ID must fail');
  console.log('PASS rejected malformed / non-HTTPS paths');
}
(async()=>{verifyPinnedCatalog();await testManhwa18();await testHotcomics();await testWebtoons();await testSecurity();})()
  .catch(error=>{console.error(error);process.exitCode=1;});
