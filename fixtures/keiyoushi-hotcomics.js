// M13-A adapter helpers; plain JavaScript ES5 for iOS 12 JavaScriptCore.
var H = (function () {
  var roots = { hot: 'https://hotcomics.io', net: 'https://manhwa18.net',
                web: 'https://www.webtoons.com' };
  function fail(done, e) { done({__sourceError: String(e && (e.message || e) || 'Source failed')}); }
  function get(url, done, headers) {
    if (!/^https:\/\//i.test(url)) { fail(done, 'Only HTTPS is permitted'); return; }
    Native.httpRequest(JSON.stringify({method:'GET',url:url,headers:headers || {Accept:'text/html,application/json'}}),function(raw) {
      try {
        var r=JSON.parse(raw);
        if (!r.ok || r.status<200 || r.status>=300) {
          fail(done, r.error || ('HTTP '+r.status + (r.status===429 ? ' — rate limited' : ''))); return;
        }
        done({body:r.body || '',url:r.finalURL || url});
      } catch(e) { fail(done,e); }
    });
  }
  function select(html,specs,done) {
    Native.htmlSelect(html,JSON.stringify(specs),function(raw){
      try { var r=JSON.parse(raw); if(r.error) fail(done,r.error); else done(r.results || {}); }
      catch(e) { fail(done,e); }
    });
  }
  function items(r,key) {return (r && r[key]) || [];}
  function field(node,key) {return (node && node.fields && node.fields[key]) || null;}
  function text(node) {return node && node.text || '';}
  function attr(node,key) {return node && node.attrs && node.attrs[key] || '';}
  function url(base,part) {return part ? Native.resolveUrl(base,part) : null;}
  function cleanURL(base,part) {
    var u=url(base,part); return u && /^https:\/\//i.test(u) ? u : null;
  }
  function slug(s) {return String(s||'').replace(/^\/+|\/+$/g,'');}
  function decodeEntities(s) {
    return String(s||'').replace(/&(#(?:x[0-9a-fA-F]+|[0-9]+)|quot|apos|amp|lt|gt|nbsp|#039);/g,function(full,e){
      var named={quot:'"',apos:"'",amp:'&',lt:'<',gt:'>',nbsp:' ', '#039':"'"};
      if(named[e]!==undefined) return named[e];
      var n=/^#x/i.test(e)?parseInt(e.substring(2),16):parseInt(e.substring(1),10);
      if(!isFinite(n)||n<0||n>65535) return full;
      return String.fromCharCode(n);
    });
  }
  function noNext() {return {items:[],hasNextPage:false};}
  return {fail:fail,get:get,select:select,items:items,field:field,text:text,
          attr:attr,url:url,cleanURL:cleanURL,slug:slug,decode:decodeEntities,noNext:noNext,roots:roots};
})();

// Unofficial HotComics port — derived from Keiyoushi Apache-2.0 source.
(function(){
  'use strict';
  var base=H.roots.hot,id='kei.hotcomics',version='0.1.0';
  var listSpec={entries:{selector:'li[itemtype*="ComicSeries"]:not(.no-comic) > a',
    fields:{title:'div.main-text > h4.title',cover:'div.visual img'}},
    next:{selector:'div.pagination a.vnext:not(.disabled)'}};
  function list(path,done) {
    H.get(base+path,function(resp){
      if(resp.__sourceError){done(resp);return;}
      H.select(resp.body,listSpec,function(res){
        if(res.__sourceError){done(res);return;}
        var seen={},rows=H.items(res,'entries').map(function(item){
          var u=H.cleanURL(base,H.attr(item,'href')),title=H.text(H.field(item,'title'));
          var cover=H.field(item,'cover'),image=H.attr(cover,'data-src')||H.attr(cover,'src');
          if(!u||!title||seen[u])return null;
          seen[u]=true;
          return {id:u,title:title,cover:H.cleanURL(base,image),url:u};
        }).filter(Boolean);
        done({items:rows,hasNextPage:H.items(res,'next').length>0});
      });
    });
  }
  function detailHTML(id,done){
    var u=H.cleanURL(base,id);
    if(!u || u.indexOf(base+'/')!==0){H.fail(done,'Invalid manga URL');return;}
    H.get(u,done);
  }
  var source={
    metadata:function(){return {id:id,name:'HotComics (experimental)',lang:'en',version:version};},
    popular:function(page,done){if(page>1){done(H.noNext());return;}list('/en',done);},
    search:function(query,page,filters,done){
      if(query){if(page>1){done(H.noNext());return;}list('/en/search?keyword='+encodeURIComponent(String(query).trim()),done);}
      else list('/en?page='+Math.max(1,page|0),done);
    },
    details:function(mangaId,done){
      detailHTML(mangaId,function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{body:{selector:'body',fields:{
          title:'h2.episode-title',writer:'p.type_box span.writer',
          genre:'p.type_box span.type',status:'p.type_box span.date',
          intro:'div.episode-contents header',description:'div.title_content > h2:not(.episode-title)'
        }}},function(res){
          if(res.__sourceError){done(res);return;}
          var b=H.items(res,'body')[0]||{},t=H.text(H.field(b,'title'));
          if(!t){H.fail(done,'HotComics title unavailable');return;}
          var status=H.text(H.field(b,'status')),genre=H.text(H.field(b,'genre'));
          done({id:mangaId,title:t,altTitles:[],cover:null,
            author:H.text(H.field(b,'writer')).replace(/^.*ⓒ\s*/,'')||null,artist:null,
            description:[H.text(H.field(b,'intro')),H.text(H.field(b,'description'))].filter(Boolean).join('\n\n'),
            status:status==='End'||status==='Ende'?'completed':(status?'ongoing':'unknown'),
            genres:genre?genre.split('/').map(function(x){return x.trim();}):[],url:mangaId});
        });
      });
    },
    chapters:function(mangaId,done){
      detailHTML(mangaId,function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{entries:{selector:'#tab-chapter a',
          fields:{name:'.cell-num',date:'.cell-time'}}},function(res){
          if(res.__sourceError){done(res);return;}
          var chapters=H.items(res,'entries').map(function(x,i){
            var click=H.attr(x,'onclick'),match=/popupLogin\(['"]([^'"]+)['"]/.exec(click);
            var u=H.cleanURL(base,match?match[1]:H.attr(x,'href'));
            if(!u)return null;
            return {id:u,name:H.text(H.field(x,'name'))||('Chapter '+(i+1)),
              number:null,volume:null,date:null,scanlator:null,language:'en',url:u};
          }).filter(Boolean);
          done(chapters.reverse());
        });
      });
    },
    pages:function(chapterId,done){
      var u=H.cleanURL(base,chapterId);
      if(!u||u.indexOf(base+'/')!==0){H.fail(done,'Invalid chapter URL');return;}
      H.get(u,function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{images:{selector:'#viewer-img img'}},function(res){
          if(res.__sourceError){done(res);return;}
          done(H.items(res,'images').map(function(x){
            return H.cleanURL(base,H.attr(x,'data-src')||H.attr(x,'src'));
          }).filter(Boolean).map(function(link,i){return {index:i,imageUrl:link,headers:{Referer:base+'/'}; }));
        });
      });
    }
  };
  this.source=source;
}).call(this);
