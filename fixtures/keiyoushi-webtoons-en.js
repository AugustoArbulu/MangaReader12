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

// Unofficial Webtoons.com English adapter — source attribution: Keiyoushi Apache-2.0.
(function(){
  'use strict';
  var base=H.roots.web,id='kei.webtoons.en',version='0.1.1';
  // The episode/series page uses og:image, but list cards can use lazy image
  // attributes and an inert data: placeholder in src. Prefer source-provided
  // actual HTTPS image URLs rather than trying to download the placeholder.
  function listCover(image) {
    var choices=[
      H.attr(image,'data-src'),
      H.attr(image,'data-original'),
      H.attr(image,'data-lazy-src'),
      H.attr(image,'data-url')
    ];
    function appendSrcSet(value) {
      if(!value)return;
      // HTML srcset is a comma-delimited list of URLs + width/density.
      var entries=value.split(',');
      for(var i=0;i<entries.length;i++){
        var token=entries[i].trim().split(/\s+/)[0];
        if(token) choices.push(token);
      }
    }
    appendSrcSet(H.attr(image,'data-srcset'));
    appendSrcSet(H.attr(image,'srcset'));
    choices.push(H.attr(image,'src'));
    for(var k=0;k<choices.length;k++){
      var u=H.cleanURL(base,choices[k]);
      if(u && /^https:\/\/(?:[a-z0-9-]+\.)*(?:webtoons\.com|pstatic\.net)(?:[/:?#]|$)/i.test(u)){
        return u;
      }
    }
    return null;
  }
  function listing(path,hasNext,done){
    H.get(base+path,function(resp){
      if(resp.__sourceError){done(resp);return;}
      H.select(resp.body,{items:{selector:'.webtoon_list li a',
        fields:{title:'.title',cover:'img'}},
        next:{selector:'a.pagination[aria-current=true] + a'}},function(res){
        if(res.__sourceError){done(res);return;}
        var seen={},entries=H.items(res,'items').map(function(x){
          var u=H.cleanURL(base,H.attr(x,'href')),title=H.text(H.field(x,'title'));
          var cover=H.field(x,'cover'),img=listCover(cover);
          if(!u||!title||seen[u])return null; seen[u]=true;
          return {id:u,title:title,cover:img,url:u};
        }).filter(Boolean);
        done({items:entries,hasNextPage:hasNext===null?H.items(res,'next').length>0:hasNext});
      });
    });
  }
  function info(id,done){
    var u=H.cleanURL(base,id);
    if(!u||u.indexOf('https://www.webtoons.com/en/')!==0){H.fail(done,'Invalid Webtoons manga link');return;}
    H.get(u,done);
  }
  var source={
    metadata:function(){return {id:id,name:'Webtoons.com EN (experimental)',lang:'en',version:version};},
    popular:function(page,done){
      var ranks=['trending','popular','originals','canvas'];
      if(page<1||page>4){done(H.noNext());return;}
      listing('/en/ranking/'+ranks[page-1],page!==4,done);
    },
    search:function(query,page,filters,done){
      var path='/en/search?keyword='+encodeURIComponent(String(query||''));
      if(page>1)path+='&page='+Math.max(1,page|0);
      listing(path,null,done);
    },
    details:function(mangaId,done){
      info(mangaId,function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{body:{selector:'body',fields:{
          title:'h1.subj, h3.subj',author:'.detail_header .info .author',
          artist:'.detail_header .info .author_area',genre:'.detail_header .info .genre',
          description:'#_asideDetail p.summary',status:'#_asideDetail p.day_info',
        }},coverMeta:{selector:'head meta[property="og:image"]'}},function(res){
          if(res.__sourceError){done(res);return;}
          var item=H.items(res,'body')[0]||{},title=H.text(H.field(item,'title'));
          if(!title){H.fail(done,'Webtoons title not found');return;}
          var st=H.text(H.field(item,'status')).toUpperCase();
          done({id:mangaId,title:title,altTitles:[],
            cover:H.cleanURL(base,H.attr(H.items(res,'coverMeta')[0],'content')),
            author:H.text(H.field(item,'author'))||null,
            artist:H.text(H.field(item,'artist'))||null,
            description:H.text(H.field(item,'description')),
            status:/UP|EVERY|NOUVEAU/.test(st)?'ongoing':(/END|COMPLETED|TERMINÉ/.test(st)?'completed':'unknown'),
            genres:H.text(H.field(item,'genre'))?[H.text(H.field(item,'genre'))]:[],url:mangaId});
        });
      });
    },
    chapters:function(mangaId,done){
      var m=/[?&]title_no=(\d+)/.exec(mangaId),titleNo=m&&m[1];
      if(!titleNo){H.fail(done,'Webtoons title_no not found');return;}
      var canvas=/\/canvas\//.test(mangaId);
      var url='https://m.webtoons.com/api/v1/'+(canvas?'canvas':'webtoon')+'/'+titleNo+
        '/episodes?pageSize=99999'+(canvas?'&readingLanguageCode=en':'');
      H.get(url,function(resp){
        if(resp.__sourceError){done(resp);return;}
        var content;try{content=JSON.parse(resp.body);}catch(e){H.fail(done,'Invalid episodes JSON');return;}
        var eps=content.result&&content.result.episodeList;
        if(!eps||!Array.isArray(eps)){H.fail(done,'Episode list unavailable');return;}
        done(eps.map(function(x,i){
          var u=H.cleanURL(base,x.viewerLink);
          if(!u)return null;
          var numberMatch=/(?:episode|chapter|ep|ch)\s*\.?\s*(\d+(?:\.\d+)?)/i.exec(x.episodeTitle||'');
          return {id:u,name:x.episodeTitle||('Episode '+(i+1)),
            number:numberMatch?Number(numberMatch[1]):null,
            volume:null,date:null,scanlator:null,language:'en',url:u};
        }).filter(Boolean).reverse());
      },{Accept:'application/json',Referer:'https://m.webtoons.com/'});
    },
    pages:function(chapterId,done){
      var u=H.cleanURL(base,chapterId);
      if(!u||!/^https:\/\/(www\.|m\.)?webtoons\.com\/en\//.test(u)){H.fail(done,'Invalid chapter URL');return;}
      H.get(u,function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{images:{selector:'div#_imageList > img'}},function(res){
          if(res.__sourceError){done(res);return;}
          var imgs=H.items(res,'images').map(function(x){
            return H.cleanURL(base,H.attr(x,'data-url'));
          }).filter(Boolean);
          if(!imgs.length){H.fail(done,'No standard images (motion toon may not be supported)');return;}
          done(imgs.map(function(url,i){
            return {index:i,imageUrl:url,headers:{Referer:'https://www.webtoons.com/'}};
          }));
        });
      });
    }
  };
  this.source=source;
}).call(this);
