// Self-contained offline tests for M13-A JS source contract (Node, no site requests).
// The HTML selector bridge is simulated at the Native boundary. It verifies
// DTO shape and URL routing, not live WebKit parsing or site availability.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function node(text='', attrs={}, fields={}) { return {text,attrs,fields}; }
function enc(o) { return JSON.stringify(o).replace(/"/g,'&quot;'); }
function runtime(filename, respond) {
  const calls=[];
  const Native={
    resolveUrl(base,part) { return new URL(part,base).href; },
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
        description:node('Description'),status:node('EVERY MONDAY'),
        thumb:node('',{content:'https://webtoon-phinf.pstatic.net/cover.jpg'})
      })]};
      if(specs.images)return {images:[node('',{'data-url':'https://webtoon-phinf.pstatic.net/page1.jpg'})]};
      throw Error('unknown DOM');
    }
  });
  assert.equal((await r.call('metadata')).id,'kei.webtoons.en');
  assert.equal((await r.call('popular',1)).items.length,1);
  assert.equal((await r.call('search','a',1,[])).items.length,1);
  assert.equal((await r.call('details',root)).status,'ongoing');
  const chapters=await r.call('chapters',root);
  assert.equal(chapters[0].number,1);
  const pages=await r.call('pages',chapters[0].id);
  assert.equal(pages.length,1);
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
(async()=>{await testManhwa18();await testHotcomics();await testWebtoons();await testSecurity();})()
  .catch(error=>{console.error(error);process.exitCode=1;});
