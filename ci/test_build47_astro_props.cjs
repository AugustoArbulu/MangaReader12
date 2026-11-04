// Validate actual native Build47 HTMLSelectorService.info body in Node.js.
// This is an offline mock of DOMParser-provided inert nodes, not a site fetch.
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const file=fs.readFileSync(path.join(__dirname,
  '../MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift'),'utf8');
const start=file.indexOf('          function info(node) {');
const end=file.indexOf('          Object.keys(specs).forEach',start);
assert(start>0 && end>start && end-start<5000);
const actualInfo=file.slice(start,end);
const sandbox=vm.createContext({});
vm.runInContext(actualInfo+'\nthis.info=info;',sandbox,{timeout:1000});
function item(tag, name, value) {
 return {localName:tag,attributes:[{name:name,value:value}],
   textContent:'No remote code executed'};
}
const longJSON=JSON.stringify([0,{title:'Comic',
  chapters:Array.from({length:500},(_,i)=>({number:i+1,title:'Chapter '+(i+1)}))}]);
assert(longJSON.length>4096,'fixture must exceed old Build46 limit');
const astro=sandbox.info(item('astro-island','props',longJSON));
assert.equal(astro.attrs.props,longJSON);
assert.equal(JSON.parse(astro.attrs.props)[1].chapters.length,500);
assert.equal(sandbox.info(item('section','props',longJSON)).attrs.props,undefined,
  'Non-Astro props must remain limited to 4096');
assert.equal(sandbox.info(item('astro-island','random',longJSON)).attrs.random,undefined,
  'Non-props attributes must stay bounded');
assert.equal(sandbox.info(item('img','srcset','x'.repeat(5000))).attrs.srcset,undefined,
  'Unrelated potentially unsafe attributes remain capped');
assert.equal(sandbox.info(item('div','data-page','a'.repeat(6000))).attrs['data-page'],
  'a'.repeat(6000),'previous data-page compatibility must remain');
assert.equal(sandbox.info(item('astro-island','props','x'.repeat(2*1024*1024+1))).attrs.props,
  undefined,'Oversized Astro props must fail closed');
assert.equal(sandbox.info(item('astro-island','props','{}')).attrs.props,'{}');
assert(file.includes('html.utf8.count <= 3 * 1024 * 1024'));
assert(file.includes('text.utf8.count <= 4 * 1024 * 1024'));
assert(file.includes('name === "chapters" ? 4000'));
assert(file.includes('name === "images" ? 1500'));
const pbx=fs.readFileSync(path.join(__dirname,
  '../MangaReader12.xcodeproj/project.pbxproj'),'utf8');
assert.equal((pbx.match(/CURRENT_PROJECT_VERSION = 47;/g)||[]).length,2);
const ui=fs.readFileSync(path.join(__dirname,
  '../MangaReader12/UI/MainTabBarController.swift'),'utf8');
assert(ui.includes('Build 47 • compatível com iOS 12.0'));
console.log('PASS Build47: native Astro props >4096 bytes, 2MB ceiling, unrelated 4KB limits, chapter/image caps, Build47');
