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

// Unofficial Manhwa18.net port — derived from Keiyoushi Apache-2.0 source.
(function () {
  'use strict';
  var base=H.roots.net, id='kei.manhwa18net', version='0.1.0';
  function page(url,done) {
    H.get(url,function(r){
      if(r.__sourceError) {done(r);return;}
      H.select(r.body,{app:{selector:'#app[data-page]'}},function(found){
        if(found.__sourceError){done(found);return;}
        var el=H.items(found,'app')[0], raw=H.attr(el,'data-page');
        if(!raw){H.fail(done,'Page data not found (#app[data-page])');return;}
        try {done(JSON.parse(H.decode(raw)).props || {});}
        catch(e){H.fail(done,'Could not parse source page data: '+e.message);}
      });
    });
  }
  function listing(path,done) {
    page(base+path,function(props){
      if(props.__sourceError){done(props);return;}
      var listing=props.paginate || props.popularManga || props.mangas || props.latestManhwaMain;
      if(!listing || !listing.data){H.fail(done,'Source listing not found');return;}
      done({items:listing.data.map(function(x){
        return {id:x.slug,title:x.name,cover:H.cleanURL(base,x.cover_url||x.thumb_url),
          url:base+'/manga/'+encodeURIComponent(x.slug)};
      }),hasNextPage:!!listing.next_page_url});
    });
  }
  function mangaPage(id,done) {
    var sl=H.slug(id).split('/')[0];
    page(base+'/manga/'+encodeURIComponent(sl),done);
  }
  function strip(s) {return String(s||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();}
  var source={
    metadata:function(){return {id:id,name:'Manhwa18.net (experimental)',lang:'en',version:version};},
    popular:function(p,done){listing('/manga-list?sort=top&page='+Math.max(1,p|0),done);},
    search:function(query,p,filters,done){
      var path=query?'/tim-kiem?q='+encodeURIComponent(String(query)):'/manga-list';
      listing(path+(path.indexOf('?')<0?'?':'&')+'page='+Math.max(1,p|0),done);
    },
    details:function(mangaId,done){
      mangaPage(mangaId,function(props){
        if(props.__sourceError){done(props);return;}
        var m=props.manga;
        if(!m){H.fail(done,'Manga details unavailable');return;}
        done({id:mangaId,title:m.name,altTitles:[],cover:H.cleanURL(base,m.cover_url||m.thumb_url),
          author:(m.artists||[]).map(function(x){return x.name;}).join(', ')||null,
          artist:(m.artists||[]).map(function(x){return x.name;}).join(', ')||null,
          description:strip(m.pilot||m.description),status:m.status_id===0?'ongoing':(m.status_id===1||m.status_id===2?'completed':'unknown'),
          genres:(m.genres||[]).map(function(x){return x.name;}),url:base+'/manga/'+encodeURIComponent(mangaId)});
      });
    },
    chapters:function(mangaId,done){
      mangaPage(mangaId,function(props){
        if(props.__sourceError){done(props);return;}
        var sl=H.slug(mangaId).split('/')[0], ch=props.chapters || [];
        done(ch.map(function(x,index){return {id:sl+'/'+x.slug,name:x.name,number:null,volume:null,
          date:x.created_at?String(x.created_at).substring(0,10):null,
          scanlator:null,language:'en',
          url:base+'/manga/'+encodeURIComponent(sl)+'/'+encodeURIComponent(x.slug)};}));
      });
    },
    pages:function(chapterId,done){
      var parts=String(chapterId).split('/');if(parts.length!==2){H.fail(done,'Invalid chapter');return;}
      page(base+'/manga/'+encodeURIComponent(parts[0])+'/'+encodeURIComponent(parts[1]),function(props){
        if(props.__sourceError){done(props);return;}
        if(!props.chapterContent){H.fail(done,'Chapter content not found');return;}
        H.select(props.chapterContent,{pages:{selector:'img'}},function(res){
          if(res.__sourceError){done(res);return;}
          done(H.items(res,'pages').map(function(node){
            return H.cleanURL(base,H.attr(node,'src')||H.attr(node,'data-src')||H.attr(node,'data-lazy-src'));
          }).filter(Boolean).map(function(u,i){return {index:i,imageUrl:u,headers:{Referer:base+'/'}}; }));
        });
      });
    }
  };
  this.source=source;
}).call(this);
