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
  var base=H.roots.web,id='kei.webtoons.en',version='0.1.11';
  // Capture only sanitized attributes of the listing response already parsed.
  // This contains neither full URLs nor titles and performs zero extra GETs.
  var coverTrace = {};
  var traceOrder = [];
  var detailTrace = {};
  var detailOrder = [];
  function kindOf(value) {
    if(!value)return 'empty';
    if(/^data:/i.test(value))return 'data';
    if(/^http:\/\//i.test(value))return 'http';
    if(/^https:\/\//i.test(value)) {
      if(/^https:\/\/(?:[a-z0-9-]+\.)*pstatic\.net(?:[\/?#]|$)/i.test(value))return 'pstatic-https';
      if(/^https:\/\/(?:[a-z0-9-]+\.)*webtoons\.com(?:[\/?#]|$)/i.test(value))return 'webtoons-https';
      return 'other-https';
    }
    if(/^\/\//.test(value))return 'protocol-relative';
    if(/^\//.test(value))return 'root-relative';
    if(/background/i.test(value))return 'css';
    return 'other';
  }
  function rememberTrace(id, card, coverURL) {
    var names=['cover','coverLazy','coverSrcset','coverHost','coverPicture','coverData','coverStyle'];
    var fields=[], attrNames=[], kinds=[], seen={};
    function inspect(node, origin) {
      if(!node)return;
      fields.push(origin);
      var attrs=node.attrs || {};
      Object.keys(attrs).sort().forEach(function(name){
        // Structural metadata only; never record any attribute value.
        if(!/^(?:src|srcset|style|data-[a-z0-9-]{1,48})$/i.test(name))return;
        var marker=origin+'.'+name;
        if(seen[marker])return;seen[marker]=true;
        if(attrNames.length>=24)return;
        attrNames.push(marker);
        kinds.push(marker+'='+kindOf(attrs[name]));
      });
    }
    inspect(card,'card');
    for(var i=0;i<names.length;i++)inspect(H.field(card,names[i]),names[i]);
    if(!Object.prototype.hasOwnProperty.call(coverTrace,id)){
      traceOrder.push(id);
      if(traceOrder.length>200)delete coverTrace[traceOrder.shift()];
    }
    // This row keeps its own immutable snapshot: a lookup by ID later might
    // retrieve a different ranking occurrence of the same series.
    var trace={
      matched:true,coverFound:!!coverURL,fields:fields.slice(0,12),
      attributes:attrNames,kinds:kinds,
      outputClass:kindOf(coverURL),outputLength:coverURL?coverURL.length:0
    };
    coverTrace[id]=trace;
    return trace;
  }
  function rememberDetail(id, node, rawContent, resolvedURL) {
    if(!Object.prototype.hasOwnProperty.call(detailTrace,id)){
      detailOrder.push(id);
      if(detailOrder.length>50)delete detailTrace[detailOrder.shift()];
    }
    detailTrace[id]={
      matched:true,metaPresent:!!node,contentPresent:!!rawContent,
      contentClass:kindOf(rawContent),resolvedFound:!!resolvedURL,
      resolvedClass:kindOf(resolvedURL)
    };
  }
  // The listing's webtoon-phinf host returned 403 on physical iOS 12.5.8.
  // The official alternate image host swebtoon-phinf served the details image
  // with normal HTTPS. Try that exact host for listing covers, preserving the
  // source-provided path and query; never rewrite unrelated image hosts.
  function canonicalListCoverURL(url) {
    return url.replace(/^https:\/\/webtoon-phinf\.pstatic\.net(?=[\/?#]|$)/i,
      'https://swebtoon-phinf.pstatic.net');
  }
  // NSURL on iOS 12 rejects literal characters that modern iOS versions
  // may automatically percent-encode. Restrict the authority to the source's
  // existing allowlist, then encode only the path/query/fragment portion.
  // Preserve reserved URL delimiters and existing valid %HH sequences.
  // Never modify other hosts, credentials, schemes, or malformed escapes.
  function normalizeWebtoonsImageURL(value, preserveHost) {
    if(!value || typeof value !== 'string')return null;
    var match=/^https:\/\/([a-z0-9-]+(?:\.[a-z0-9-]+)*)(?=\/|\?|#|$)/i.exec(value);
    if(!match)return null;
    var host=match[1].toLowerCase();
    var allowed=host==='webtoons.com' || host.slice(-13)==='.webtoons.com' ||
      host==='pstatic.net' || host.slice(-12)==='.pstatic.net';
    if(!allowed)return null;
    var rest=value.substring(match[0].length);
    // Do not repair controls, bidi formatting, bad percent escapes, or any
    // unexpected credentials/port/host syntax.
    if(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/.test(rest) ||
       /%(?![a-f0-9]{2})/i.test(rest))return null;
    var encoded;
    try {
      encoded=encodeURI(rest).replace(/%25(?=[a-f0-9]{2})/ig,'%');
    } catch(e) {
      return null; // e.g. malformed surrogate pair
    }
    var normalized=match[0]+encoded;
    return preserveHost ? normalized : canonicalListCoverURL(normalized);
  }
  // The episode/series page uses og:image, but list cards can use lazy image
  // attributes and an inert data: placeholder in src. Prefer source-provided
  // actual HTTPS image URLs rather than trying to download the placeholder.
  function listCover(image) {
    if(!image)return null;
    var choices=[
      H.attr(image,'data-src'),
      H.attr(image,'data-original'),
      H.attr(image,'data-lazy-src'),
      H.attr(image,'data-src-lazy'),
      H.attr(image,'data-url'),
      H.attr(image,'data-image'),
      H.attr(image,'data-image-url'),
      H.attr(image,'data-thumbnail'),
      H.attr(image,'data-thumbnail-url'),
      H.attr(image,'data-thumb'),
      H.attr(image,'data-thumb-url'),
      H.attr(image,'data-cover'),
      H.attr(image,'data-cover-url'),
      H.attr(image,'data-background'),
      H.attr(image,'data-background-image'),
      H.attr(image,'data-bg')
    ];
    function appendSrcSet(value) {
      if(!value)return;
      var entries=value.split(',');
      for(var i=0;i<entries.length;i++){
        var token=entries[i].trim().split(/\s+/)[0];
        if(token)choices.push(token);
      }
    }
    appendSrcSet(H.attr(image,'data-srcset'));
    appendSrcSet(H.attr(image,'srcset'));
    choices.push(H.attr(image,'src'));
    // Read only inert attributes. Never execute inline CSS or site scripts.
    var style=H.attr(image,'style');
    var bg=/\bbackground(?:-image)?\s*:\s*url\(\s*(?:"([^"]+)"|'([^']+)'|([^)]*))\s*\)/i.exec(style);
    if(bg)choices.push((bg[1]||bg[2]||bg[3]||'').trim());
    for(var k=0;k<choices.length;k++){
      var u=normalizeWebtoonsImageURL(H.cleanURL(base,choices[k]));
      if(u)return u;
    }
    return null;
  }
  function listCardCover(card) {
    // Scan bounded alternatives within the same series card. No per-item
    // details() or extra HTTP calls for empty thumbnails.
    var fields=['cover','coverLazy','coverSrcset','coverHost','coverPicture',
                'coverData','coverStyle'];
    for(var i=0;i<fields.length;i++){
      var u=listCover(H.field(card,fields[i]));
      if(u)return u;
    }
    return listCover(card);
  }
  function listingTags(card) {
    // Do not infer content labels from title, artwork or the current genre
    // route. Only use explicit classification shown on this listing card.
    var raw=H.text(H.field(card,'genre'));
    if(!raw)return null;
    var tags=raw.split(/[,|\/•]+/).map(function(t){return t.trim();})
      .filter(function(t){return t.length>0&&t.length<=48;}).slice(0,12);
    return tags.length?tags:null;
  }
  function listing(path,hasNext,done){
    H.get(base+path,function(resp){
      if(resp.__sourceError){done(resp);return;}
      H.select(resp.body,{items:{selector:'.webtoon_list li a, .card_list li a, .genre_list li a',
        fields:{title:'.title, .subj',genre:'.genre, .tag, [data-genre]',cover:'img',
          coverLazy:'img[data-src],img[data-original],img[data-lazy-src],img[data-url]',
          coverSrcset:'img[srcset],img[data-srcset]',
          coverHost:'img[src*="pstatic.net"],img[src*="webtoons.com"]',
          coverPicture:'picture source[srcset],picture source[data-srcset]',
          coverData:'[data-thumbnail],[data-cover],[data-image],[data-bg]',
          coverStyle:'[style*="background-image"],[style*="background:"]'}},
        next:{selector:'a.pagination[aria-current=true] + a'}},function(res){
        if(res.__sourceError){done(res);return;}
        var seen={},entries=H.items(res,'items').map(function(x){
          var u=H.cleanURL(base,H.attr(x,'href')),title=H.text(H.field(x,'title'));
          var img=listCardCover(x);
          if(!u||!title||seen[u])return null; seen[u]=true;
          var diagnostic=rememberTrace(u,x,img);
          return {id:u,title:title,cover:img,url:u,
            coverDiagnostic:diagnostic,tags:listingTags(x)};
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
    // Optional diagnostic method invoked only after the user explicitly
    // swipes a selected manga row. No fresh website request.
    inspectCover:function(mangaId) {
      return coverTrace[mangaId] || {
        matched:false,coverFound:false,fields:[],attributes:[],kinds:[],
        outputClass:'empty',outputLength:0
      };
    },
    inspectDetailsCover:function(mangaId) {
      return detailTrace[mangaId] || {
        matched:false,metaPresent:false,contentPresent:false,
        contentClass:'empty',resolvedFound:false,resolvedClass:'empty'
      };
    },
    metadata:function(){return {id:id,name:'Webtoons.com EN (experimental)',lang:'en',version:version};},
    // Optional discovery API. Rankings are *categories*, not page 1..4.
    // Genre pages are real site listings; their DOM still needs iOS12 QA.
    // Latest is restricted to today's Originals updates (Keiyoushi route).
    // A deliberately bounded, opt-in classification sample from the
    // platform's public CANVAS BL/GL list. Only a single first-page GET
    // happens after the user explicitly taps Verify in the app. This does
    // not describe all BL/GL titles or Original works.
    classificationSample:function(done){
      H.get(base+'/en/canvas/list?genreTab=BL_GL',function(resp){
        if(resp.__sourceError){done(resp);return;}
        H.select(resp.body,{entries:{
          selector:'.card_lst li a, .card_list li a, .webtoon_list li a, .genre_list li a, #_listUl li a'
        }},function(res){
          if(res.__sourceError){done(res);return;}
          var seen={},numbers=[];
          H.items(res,'entries').forEach(function(entry){
            var link=H.cleanURL(base,H.attr(entry,'href'));
            if(!link||link.indexOf(base+'/en/canvas/')!==0)return;
            var found=/(?:[?&])title_no=([0-9]{1,12})(?:[&#]|$)/.exec(link);
            if(!found||seen[found[1]]||numbers.length>=60)return;
            seen[found[1]]=true;numbers.push(found[1]);
          });
          if(!numbers.length){
            H.fail(done,'CANVAS BL/GL listing did not expose series IDs');
            return;
          }
          done({source:'canvas-blgl-first-page',
                complete:false,titleNumbers:numbers});
        });
      });
    },
    browseCategories:function(){
      return [
        {id:'trending',title:'Tendências',kind:'ranking'},
        {id:'originals',title:'Originals',kind:'ranking'},
        {id:'canvas',title:'Canvas',kind:'ranking'},
        {id:'latest',title:'Recentes (Originals do dia)',kind:'latest'},
        {id:'romance',title:'Romance',kind:'genre'},
        {id:'fantasy',title:'Fantasia',kind:'genre'},
        {id:'action',title:'Ação',kind:'genre'},
        {id:'drama',title:'Drama',kind:'genre'},
        {id:'comedy',title:'Comédia',kind:'genre'},
        {id:'thriller',title:'Suspense',kind:'genre'},
        {id:'mystery',title:'Mistério',kind:'genre'}
      ];
    },
    // The v1 popular(page) method now serves a single ranking rather than
    // treating each integer page as an unrelated category. All rankings
    // have a bounded first page unless the adapter verifies true pagination.
    popular:function(page,done){
      if(page!==1){done(H.noNext());return;}
      listing('/en/ranking/popular',false,done);
    },
    browse:function(mode,page,done){
      if(page!==1){done(H.noNext());return;}
      var rankings={trending:1,originals:1,canvas:1};
      var genres={romance:1,fantasy:1,action:1,drama:1,
                  comedy:1,thriller:1,mystery:1};
      if(mode==='latest'){
        // Mirrors Keiyoushi Webtoons.getLatestUpdates(): the site's
        // current weekday Originals listing ordered by chapter updates.
        // It is NOT a claim to list all updates across Canvas or all days.
        var days=['sunday','monday','tuesday','wednesday',
                  'thursday','friday','saturday'];
        var day=days[(new Date()).getDay()];
        listing('/en/originals/'+day+'?sortOrder=UPDATE',false,done);
      } else if(Object.prototype.hasOwnProperty.call(rankings,mode)){
        listing('/en/ranking/'+mode,false,done);
      } else if(Object.prototype.hasOwnProperty.call(genres,mode)){
        listing('/en/genres/'+mode,false,done);
      } else {
        H.fail(done,'Unsupported discovery category');
      }
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
          var meta=H.items(res,'coverMeta')[0],rawMeta=H.attr(meta,'content');
          var detailsCover=normalizeWebtoonsImageURL(H.cleanURL(base,rawMeta));
          rememberDetail(mangaId,meta,rawMeta,detailsCover);
          done({id:mangaId,title:title,altTitles:[],
            cover:detailsCover,
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
            // Chapter media may use a different CDN path than thumbnail
            // covers. Preserve the original allowed host and image order.
            // Resolve relative media links against the loaded chapter page,
            // not against the catalog home page.
            var resolved=H.cleanURL(resp.url || u,H.attr(x,'data-url'));
            return normalizeWebtoonsImageURL(resolved,true);
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
