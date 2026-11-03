// Build44 native HTML selector regression test.
// Runs the exact JavaScript evaluator embedded in Swift against synthetic
// DOM fixtures; makes no network requests and does not use site HTML.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const swift = fs.readFileSync(path.join(__dirname,
  '../MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift'), 'utf8');
const anchor = '        let script = """\n';
const endMarker = '\n        """\n        browser.evaluateJavaScript';
const from = swift.indexOf(anchor, swift.indexOf('private final class HTMLSelectorService'));
const until = swift.indexOf(endMarker, from);
assert(from !== -1 && until > from, 'HTML selector JavaScript not found in Swift');
const embedded = swift.slice(from + anchor.length, until);
assert(embedded.includes('name === "chapters" ? 4000'),
  'chapter-specific bounded limit must remain explicit');
assert(embedded.includes('name === "images" ? 1500'),
  'image-specific bounded limit must remain explicit');
assert(!embedded.includes('Math.min(200, matches.length)'),
  'do not silently truncate the first 200 chapters');
assert(embedded.includes('Refusing an incomplete list.'),
  'oversized chapter and image lists must fail instead of truncating');

function domNode(text, attrs={}, fields={}) {
  return {
    textContent:text,
    attributes:Object.keys(attrs).map(key=>({name:key,value:attrs[key]})),
    querySelector(selector) { return fields[selector] || null; }
  };
}
function createNodes(count, kind) {
  return Array.from({length:count},(_,i)=>{
    if (kind==='chapters') {
      return domNode('Chapter '+(count-i),
        {href:'/chapters/'+String(count-i).padStart(4,'0')}, {
          'span.flex > span':domNode('Chapter '+(count-i)),
          'time[datetime]':domNode('',{datetime:'2026-01-01T00:00:00Z'}),
          'img':domNode('',{src:'/static/images/chapter-badge.svg'})
        });
    }
    return domNode('',{src:'/images/'+(i+1)+'.jpg'});
  });
}
function run(name, count, options={}) {
  const selector = name==='chapters' ? 'div[x-data] > a' : '#chapter-images img';
  const specs = {[name]:{selector, fields:name==='chapters'?{
    name:'span.flex > span',date:'time[datetime]',official:'img'
  }:{}}};
  const replacements = [
    ['\\(htmlLiteral)',JSON.stringify('<!doctype html><html><body>offline</body></html>')],
    ['\\(selectorsLiteral)',JSON.stringify(JSON.stringify(specs))]
  ];
  let script = embedded;
  for (const [needle, value] of replacements) {
    assert(script.includes(needle), 'missing Swift interpolation '+needle);
    script = script.replace(needle,value);
  }
  const nodes = options.nodes || createNodes(count,name);
  const fakeDOM = class {
    parseFromString(html, mime) {
      assert.equal(mime,'text/html');
      assert(html.includes('offline'));
      return {
        querySelectorAll(actual) {
          assert.equal(actual,selector);
          return nodes;
        }
      };
    }
  };
  return vm.runInNewContext(script,{DOMParser:fakeDOM,JSON,Object,Math},{timeout:3000});
}

// The physical One Piece report shows only 998..1197, exactly 200 of
// the newest chapters. A full HTML selector result must preserve all 1197
// elements and IDs in their original order.
const full = JSON.parse(run('chapters',1197));
assert.equal(full.results.chapters.length,1197);
assert.equal(full.results.chapters[0].fields.name.text,'Chapter 1197');
assert.equal(full.results.chapters[1196].fields.name.text,'Chapter 1');
assert.equal(full.results.chapters[1196].attrs.href,'/chapters/0001');

// A large image set also must not cut at the legacy 200-item limit.
const pages = JSON.parse(run('images',350));
assert.equal(pages.results.images.length,350);
assert.equal(pages.results.images[349].attrs.src,'/images/350.jpg');

// Keep a strict bound for ordinary listing selector results on old devices.
const listing = JSON.parse(run('items',250));
assert.equal(listing.results.items.length,200);

// When the safe ceiling is exceeded, fail with an explicit diagnostic;
// never report an incomplete subset as a complete chapter/page list.
assert.throws(()=>run('chapters',4001),/Refusing an incomplete list/);
assert.throws(()=>run('images',1501),/Refusing an incomplete list/);

// The existing serialized output limit remains in place on iOS 12.
assert(swift.includes('text.utf8.count <= 4 * 1024 * 1024'),
  'serialized selector JSON output must stay bounded');
assert(swift.includes('html.utf8.count <= 3 * 1024 * 1024'),
  'HTML input must stay bounded');

const pbx = fs.readFileSync(path.join(__dirname,
  '../MangaReader12.xcodeproj/project.pbxproj'),'utf8');
assert.equal((pbx.match(/CURRENT_PROJECT_VERSION = 44;/g)||[]).length,2,
  'both Debug and Release must be Build 44');

console.log('PASS Build44 offline: 1197 chapters, 350 images, normal 200 cap, explicit overflow, iOS12 input/output bounds');
