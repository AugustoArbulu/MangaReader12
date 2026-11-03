// Asura Scans EN source-only pilot tests. No requests to the live site.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const vm=require('node:vm');

const script=fs.readFileSync(path.join(__dirname,'../fixtures/keiyoushi-asurascans-en.js'),'utf8');
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,
  '../fixtures/asurascans-pilot-repository.json'),'utf8'));
const manifest=catalog.sources[0];
assert.equal(catalog.sources.length,1);
assert.equal(manifest.id,'kei.asurascans.en');
assert.equal(manifest.version,'0.1.0');
assert.deepEqual(manifest.domains,['asurascans.com','api.asurascans.com']);
assert.equal(crypto.createHash('sha256').update(script).digest('hex'),manifest.sha256);
assert(!/access_token|X-Page-Token|Authorization:|cloudflare|bypass|webdriver/i.test(script));
const BASE='https://asurascans.com';
const API='https://api.asurascans.com/api';
const A=BASE+'/comics/sample-comic-zx91a2b3';
const CH1=A+'/chapter/1';
const CH2=A+'/chapter/2';
const item=(attrs={})=>({text:'',attrs,fields:{}});

const DETAILS={
  title:'Sample Comic',description:'<p>Sample <b>description</b> text.</p>',
  coverUrl:'https://asurascans.com/covers/100.jpg',
  author:'Sample Author',artist:'Sample Artist',type:'manhwa',
  status:'ongoing',
  alternativeTitles:'Sample Alias • Test Alias',
  genres:[{name:'Action'},{name:'Romance'},{name:'Action'}]
};
const CHAPTERS={
  chapters:[
    {number:2,title:'The Return',created_at:'2026-09-02T00:00:00Z',
      is_premium:false},
    {number:1,created_at:'2026-08-01T00:00:00Z',
      is_locked:false},
    {number:3,is_premium:true},
    {number:4,early_access_until:'2099-10-01T00:00:00Z'},
    {number:5,early_access_until:'invalid date'},
    {number:2,title:'Duplicate'}
  ]
};
const PROPS={details:JSON.stringify([0,DETAILS]),chapters:JSON.stringify({
  chapters:[0,CHAPTERS.chapters]
})};
const pageInfo={pages:[
 {url:'https://asurascans.com/chapters/1/01.jpg'},
 {url:'https://api.asurascans.com/static/images/02.png'}
]};
function createRuntime(config={}) {
 const calls=[], selectors=[], state={};
 const native={
  resolveUrl(base,ref){return new URL(ref,base).href;},
  storageGet(key){return state[key]||null;},
  storageSet(key,val){state[key]=val;},
  httpRequest(raw,done){
   const req=JSON.parse(raw);calls.push(req);
   let data;
   if(config.request) data=config.request(req);
   else if(req.url.startsWith(API+'/series?')) data={
    body:JSON.stringify({data:[
      {title:'Sample Comic',public_url:'/comics/sample-comic-zx91a2b3',
        cover:'https://asurascans.com/covers/100.jpg'},
      {title:'Ignored',public_url:'https://evil.invalid/comics/abc',
        cover:'https://evil.invalid/cover.jpg'}
    ],meta:{has_more:true}})
   };
   else if(req.url===A) data={body:'SERIES'};
   else if(req.url===CH1) data={body:'PAGES'};
   else throw Error('Unexpected HTTP: '+req.url);
   if(typeof data==='string')data={body:data};
   done(JSON.stringify({ok:data.ok!==false,status:data.status||200,
     body:data.body||'',finalURL:data.finalURL||req.url,error:data.error}));
  },
  htmlSelect(html,raw,done) {
   const spec=JSON.parse(raw);selectors.push(spec);
   let results;
   if(config.select)results=config.select(html,spec);
   else if(html==='SERIES'){
    assert(spec.details&&spec.chapters);
    results={details:[item({props:PROPS.details})],
      chapters:[item({props:PROPS.chapters})]};
   } else if(html==='PAGES') {
    assert(spec.pages);
    results={pages:[item({props:JSON.stringify([0,pageInfo])})]};
   } else throw Error('Unexpected HTML '+html);
   done(JSON.stringify({results}));
  }
 };
 const context=vm.createContext({Native:native,console,Date});
 new vm.Script(script,{filename:'keiyoushi-asurascans-en.js'}).runInContext(context);
 const source=context.source;
 for(const name of ['metadata','popular','search','details','chapters','pages',
    'browseCategories','browse']) assert.equal(typeof source[name],'function');
 function call(name,...params) {
  return new Promise((resolve,reject)=>{
   try {
    const value=source[name](...params,resolve);
    if(value!==undefined)resolve(value);
   }catch(e){reject(e);}
  });
 }
 return {call,calls,selectors,state};
}
async function main(){
 const r=createRuntime();
 const meta=await r.call('metadata');
 assert.equal(meta.name,'Asura Scans EN (experimental)');
 const popular=await r.call('popular',1);
 assert.equal(popular.items.length,1);
 assert.equal(popular.items[0].id,A);
 assert.equal(popular.items[0].cover,BASE+'/covers/100.jpg');
 assert.equal(popular.hasNextPage,true);
 assert.match(r.calls[0].url,/sort=popular/);
 assert.equal(r.calls[0].headers.Accept,'application/json');
 const query=await r.call('search','Sample 1',2,[]);
 assert.equal(query.items[0].title,'Sample Comic');
 assert.match(r.calls[1].url,/offset=20/);
 assert.match(r.calls[1].url,/search=Sample%201/);
 assert.match(r.calls[1].url,/sort=latest/);
 const latest=await r.call('browse','latest',3);
 assert.equal(latest.items.length,1);
 assert.match(r.calls[2].url,/sort=latest/);
 assert.match(r.calls[2].url,/offset=40/);
 const cats=await r.call('browseCategories');
 assert.deepEqual(Array.from(cats).map(c=>c.id),['popular','latest']);
 const before=r.calls.length;
 const pair=await Promise.all([r.call('details',A),r.call('chapters',A)]);
 const details=pair[0],chapters=pair[1];
 assert.equal(r.calls.length,before+1,'details and chapters should coalesce a single series GET');
 assert.equal(details.id,A);
 assert.equal(details.title,'Sample Comic');
 assert.equal(details.author,'Sample Author');
 assert.equal(details.artist,'Sample Artist');
 assert.equal(details.status,'ongoing');
 assert.equal(details.description,'Sample description text.');
 assert.deepEqual(Array.from(details.genres),['Manhwa','Action','Romance']);
 assert.deepEqual(Array.from(details.altTitles),['Sample Alias','Test Alias']);
 assert.equal(details.cover,BASE+'/covers/100.jpg');
 assert.equal(chapters.length,2,'hide premium, early-access and invalid windows');
 assert.equal(chapters[0].id,CH1);
 assert.equal(chapters[0].date,'2026-08-01T00:00:00Z');
 assert.equal(chapters[1].id,CH2);
 assert.equal(chapters[1].name,'Chapter 2 - The Return');
 assert.equal(chapters[1].number,2);
 assert.equal(chapters[1].date,'2026-09-02T00:00:00Z');
 // Returning to details should reuse cached props, no new GET.
 await r.call('details',A);
 assert.equal(r.calls.length,before+1);
 const pages=await r.call('pages',CH1);
 assert.equal(pages.length,2);
 assert.equal(pages[1].imageUrl,'https://api.asurascans.com/static/images/02.png');
 assert.equal(pages[0].headers.Referer,BASE+'/');
 assert.equal(pages[1].index,1);
 const prior=r.calls.length;
 for(const [method,arg] of [['details','https://evil.invalid/comics/xyz'],
   ['chapters','http://asurascans.com/comics/xyz'],
   ['pages','https://asurascans.com/comics/a/chapters/1']]){
  assert((await r.call(method,arg)).__sourceError);
 }
 assert((await r.call('search','x',1,{status:'ongoing'})).__sourceError);
 assert((await r.call('browse','unknown',1)).__sourceError);
 assert.equal(r.calls.length,prior,'invalid params never fetch the network');
 // Scrambled tiles must fail: never pretend raw page is readable or downloadable.
 const tiled=createRuntime({select(html,spec){
  assert(spec.pages);return {pages:[item({props:JSON.stringify({
   pages:[{url:'https://asurascans.com/scrambled.jpg',tiles:[1,0],
    tile_cols:2,tile_rows:1}]})})]};
 }});
 const scrambled=await tiled.call('pages',CH1);
 assert(scrambled.__sourceError.includes('tiled images'));
 assert.equal(tiled.calls.length,1);
 // Free public page list absent; no auth/cookie fallback or endpoint guesses.
 const premium=createRuntime({select(){return {pages:[item({
  props:JSON.stringify({pages:[]})
 })]};}});
 assert((await premium.call('pages',CH1)).__sourceError.includes('no publicly accessible pages'));
 assert.equal(premium.calls.length,1);
 const external=createRuntime({select(){return {pages:[item({
  props:JSON.stringify({pages:[
   {url:'https://external.cdn.invalid/image1.jpg?token=PRIVATE'},
   {url:'https://asurascans.com/chapters/1/02.jpg'}]})
 })]};}});
 const denied=await external.call('pages',CH1);
 assert(denied.__sourceError.includes('external.cdn.invalid'));
 assert(!denied.__sourceError.includes('PRIVATE'));
 assert(!denied.__sourceError.includes('/image1'));
 // HTTP 403 and redirects: return error without retries or cross-host GET.
 const blocked=createRuntime({request(){return {status:403,ok:false,body:'Denied'};}});
 assert((await blocked.call('popular',1)).__sourceError.includes('403'));
 assert.equal(blocked.calls.length,1);
 const redirected=createRuntime({request(){return {body:'ignored',
  finalURL:'https://evil.invalid/x'};}});
 assert((await redirected.call('popular',1)).__sourceError.includes('Redirect'));
 assert.equal(redirected.calls.length,1);
 // Native HTTP allowlist and stable source ID remain explicit.
 assert(script.includes("var api = 'https://api.asurascans.com/api'"));
 assert(!script.includes('document.cookie'));
 assert(!script.includes('Authorization'));
 console.log('PASS Asura offline: public API, pagination, Astro details, 2 public chapters, dates, source cache, public images, premium and tiled fail-closed');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
