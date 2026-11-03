// Asura Scans EN candidate for MangaReader12 Source API v1 on iOS 12.
// Reference: keiyoushi/extensions-source src/en/asurascans (Apache-2.0).
// Offline-pilot only. Public series API and inert Astro props: no login,
// auth cookies, premium tokens, CAPTCHA, WebView scripts or WAF automation.
// Scrambled (tile-shuffled) pages are deliberately NOT returned unprocessed.
(function () {
  'use strict';

  var site = 'https://asurascans.com';
  var api = 'https://api.asurascans.com/api';
  var sourceID = 'kei.asurascans.en';
  var version = '0.1.1';
  var PER_PAGE = 20;
  var siteRE = /^https:\/\/(?:www\.)?asurascans\.com(?=\/|[?#]|$)/i;
  var apiRE = /^https:\/\/api\.asurascans\.com(?=\/|[?#]|$)/i;
  var seriesRE = /^https:\/\/(?:www\.)?asurascans\.com\/comics\/([A-Za-z0-9-]{1,180})\/?(?:[?#].*)?$/i;
  var stableSeriesRE = /^https:\/\/(?:www\.)?asurascans\.com\/series\/([A-Za-z0-9-]{1,180})\/?(?:[?#].*)?$/i;
  var chapterRE = /^https:\/\/(?:www\.)?asurascans\.com\/comics\/([A-Za-z0-9-]{1,180})\/chapter\/([0-9]+(?:\.[0-9]+)?)\/?(?:[?#].*)?$/i;
  var stableChapterRE = /^https:\/\/(?:www\.)?asurascans\.com\/series\/([A-Za-z0-9-]{1,180})\/chapter\/([0-9]+(?:\.[0-9]+)?)\/?(?:[?#].*)?$/i;
  var cache = {};
  var cachedAt = {};
  var pending = {};

  function fail(done, reason) {
    done({__sourceError: String(reason && reason.message || reason || 'Asura source error')});
  }
  function hostname(url) {
    var match = /^https:\/\/([a-z0-9.-]+)(?=\/|[?#]|$)/i.exec(url || '');
    return match ? match[1].toLowerCase() : null;
  }
  function resolve(origin, value) {
    if (typeof value !== 'string' || !value ||
        /[\u0000-\u001f\u007f]/.test(value)) return null;
    var url = Native.resolveUrl(origin, value);
    return typeof url === 'string' && /^https:\/\//i.test(url) ? url : null;
  }
  function validSlug(value) {
    return typeof value === 'string' && /^[A-Za-z0-9-]{1,180}$/.test(value);
  }
  function stableSeriesURL(slug) {
    return validSlug(slug) ? site + '/series/' + slug : null;
  }
  function publicSeriesURL(value) {
    var url = resolve(site + '/', value);
    var match = url && seriesRE.exec(url);
    return match ? site + '/comics/' + match[1] : null;
  }
  function seriesURL(value) {
    var url = resolve(site + '/', value);
    var stable = url && stableSeriesRE.exec(url);
    return stable ? stableSeriesURL(stable[1]) : publicSeriesURL(value);
  }
  function chapterURL(value) {
    var url = resolve(site + '/', value);
    var stable = url && stableChapterRE.exec(url);
    if (stable) return stableSeriesURL(stable[1]) + '/chapter/' + stable[2];
    var match = url && chapterRE.exec(url);
    return match ? site + '/comics/' + match[1] + '/chapter/' + match[2] : null;
  }
  function savePublicAlias(stableURL, publicURL) {
    var stable = stableSeriesRE.exec(stableURL || '');
    var actual = publicSeriesURL(publicURL);
    if (stable && actual) {
      // Store only ordinary public series URL aliases (no auth, tokens,
      // signed page paths or cookies) in the source's own namespace.
      Native.storageSet('asura-public-v1:' + stable[1], actual);
    }
  }
  function publicAlias(stableURL) {
    var stable = stableSeriesRE.exec(stableURL || '');
    if (!stable) return publicSeriesURL(stableURL);
    var saved = Native.storageGet('asura-public-v1:' + stable[1]);
    // If the device has no saved alias, use the site's public comics path
    // without a random suffix. The server may redirect to the current one.
    return publicSeriesURL(saved) || site + '/comics/' + stable[1];
  }
  function publicChapterURL(id) {
    var canonical = chapterURL(id);
    var stable = canonical && stableChapterRE.exec(canonical);
    if (stable) {
      return publicAlias(stableSeriesURL(stable[1])) + '/chapter/' + stable[2];
    }
    return canonical;
  }
  function safeImage(value) {
    var url = resolve(site + '/', value);
    // The media CDN inventory is NOT yet verified; allow only documented
    // site and API origins until physical observation/review.
    if (!url) return {url: null, host: null};
    var host = hostname(url);
    return {url: siteRE.test(url) || apiRE.test(url) ? url : null, host: host};
  }
  function request(url, accept, done) {
    if (!siteRE.test(url) && !apiRE.test(url)) {
      fail(done, 'Request outside Asura HTTPS origins'); return;
    }
    Native.httpRequest(JSON.stringify({
      method: 'GET', url: url,
      headers: {Accept: accept || 'text/html'}
    }), function (raw) {
      try {
        var resp = JSON.parse(raw);
        if (!resp.ok || !(resp.status >= 200 && resp.status < 300)) {
          fail(done, resp.error || ('Asura HTTP ' + resp.status)); return;
        }
        if (!siteRE.test(resp.finalURL || url) &&
            !apiRE.test(resp.finalURL || url)) {
          fail(done, 'Redirect outside permitted Asura origin'); return;
        }
        done({body: resp.body || '', finalURL: resp.finalURL || url});
      } catch (e) { fail(done, 'Invalid native HTTP response'); }
    });
  }
  function parseJSON(body, done) {
    try { return JSON.parse(body); }
    catch (e) { fail(done, 'Invalid Asura JSON response'); return null; }
  }
  function select(html, selectors, done) {
    Native.htmlSelect(html, JSON.stringify(selectors), function (raw) {
      try {
        var data = JSON.parse(raw);
        if (data.error) { fail(done, data.error); return; }
        done(data.results || {});
      } catch (e) { fail(done, 'Invalid Asura HTML selection response'); }
    });
  }
  function list(result, name) {
    return result && result[name] || [];
  }
  function attr(item, name) {
    return item && item.attrs && item.attrs[name] || '';
  }
  function cleanText(text) {
    return String(text || '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;|&#160;/gi, ' ')
      .replace(/&amp;/gi, '&').replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>').replace(/\s+/g, ' ').trim();
  }
  function parseNumber(value, low, high) {
    var n = Number(value);
    return isFinite(n) && n >= low && n <= high ? n : null;
  }
  function isoDate(value) {
    return typeof value === 'string' &&
      /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value)
        ? value : null;
  }
  function unAstro(node, depth) {
    if (depth > 48) throw new Error('Astro payload too deeply nested');
    if (node === null || typeof node !== 'object') return node;
    if (Object.prototype.toString.call(node) === '[object Array]') {
      if (node.length === 1 && typeof node[0] === 'number') return null;
      if (node.length === 2 && typeof node[0] === 'number') {
        return unAstro(node[1], depth + 1);
      }
      return node.map(function (x) { return unAstro(x, depth + 1); });
    }
    var output = {}, keys = Object.keys(node);
    if (keys.length > 3000) throw new Error('Astro object too large');
    keys.forEach(function (key) {
      // A two-integer permutation [1,0] is valid tile metadata, NOT an
      // Astro tagged pair. Preserve it so pages() always fails closed.
      var value = node[key];
      if (key === 'tiles' &&
          Object.prototype.toString.call(value) === '[object Array]' &&
          value.every(function (v) {return typeof v === 'number';})) {
        output[key] = value.slice();
      } else {
        output[key] = unAstro(value, depth + 1);
      }
    });
    return output;
  }
  function astroProp(item) {
    var value = attr(item, 'props');
    if (typeof value !== 'string' || value.length > 2500000) {
      throw new Error('Astro property missing or too large');
    }
    return unAstro(JSON.parse(value), 0);
  }
  function findAstro(details, name) {
    var candidates = list(details, name);
    if (!candidates.length) return null;
    return astroProp(candidates[0]);
  }
  function detailsInfo(info, canonical, fallbackName) {
    if (!info || typeof info !== 'object' ||
        typeof info.title !== 'string' || !info.title.trim()) {
      throw new Error('Asura series details missing title');
    }
    var genres = [];
    function genre(name) {
      if (typeof name !== 'string') return;
      name = name.trim();
      if (name && name.length < 80 && genres.indexOf(name) < 0) genres.push(name);
    }
    genre(info.type ? String(info.type).replace(/^\w/, function (c) {
      return c.toUpperCase();
    }) : '');
    if (Object.prototype.toString.call(info.genres) === '[object Array]') {
      info.genres.forEach(function (entry) {genre(entry && entry.name);});
    }
    var image = safeImage(info.coverUrl);
    var statuses = {ongoing:'ongoing',completed:'completed',hiatus:'hiatus',
      dropped:'cancelled',axed:'cancelled'};
    var altTitles = [];
    if (typeof info.alternativeTitles === 'string') {
      var raw = info.alternativeTitles;
      (raw.indexOf('•') >= 0 ? raw.split('•') : raw.split(',')).forEach(function (t) {
        t=t.trim(); if(t && t.length<200 && altTitles.indexOf(t)<0)altTitles.push(t);
      });
    }
    return {
      id: canonical,
      title: info.title.trim(),
      altTitles: altTitles,
      cover: image.url,
      author: typeof info.author === 'string' ? cleanText(info.author) : null,
      artist: typeof info.artist === 'string' ? cleanText(info.artist) : null,
      description: cleanText(info.description),
      status: statuses[String(info.status || '').toLowerCase()] || 'unknown',
      genres: genres,
      url: canonical
    };
  }
  function isLocked(chapter) {
    if (chapter.is_premium === true || chapter.is_locked === true) return true;
    if (chapter.early_access_until == null || chapter.early_access_until === '') return false;
    var time = Date.parse(chapter.early_access_until);
    // Ambiguous early-access windows are conservatively omitted.
    return !isFinite(time) || time > Date.now();
  }
  function formatNumber(number) {
    var n = parseNumber(number, 0, 999999);
    if (n === null) return null;
    return String(n);
  }
  function chapterList(info, canonical) {
    if (!info || Object.prototype.toString.call(info.chapters) !== '[object Array]') {
      throw new Error('Asura chapters property is missing');
    }
    var output = [], seen = {};
    for (var i = 0; i < info.chapters.length; i++) {
      var chapter = info.chapters[i];
      if (!chapter || isLocked(chapter)) continue;
      var num = formatNumber(chapter.number);
      if (num === null) continue;
      var url = chapterURL(canonical + '/chapter/' + num);
      if (!url || seen[url]) continue;
      seen[url] = true;
      var name = 'Chapter ' + num;
      if (typeof chapter.title === 'string' && chapter.title.trim()) {
        name += ' - ' + cleanText(chapter.title);
      }
      output.push({id: url, name: name, number: Number(num), volume: null,
        date: isoDate(chapter.created_at), scanlator: null,
        language: 'en', url: publicChapterURL(url) || url});
    }
    // Existing reader/Library support this order; avoid inventing omitted
    // premium chapters or re-numbering public IDs.
    return output.reverse();
  }
  function seriesData(canonical, done) {
    // In a single details view, native UIKit requests details+chapters in
    // parallel. Coalesce the same public HTML GET to stay within source rate.
    var now = Date.now();
    if (cache[canonical] && now - cachedAt[canonical] < 30000) {
      done(cache[canonical]); return;
    }
    if (pending[canonical]) { pending[canonical].push(done); return; }
    pending[canonical] = [done];
    var target = publicAlias(canonical);
    if (!target) {
      var invalid = pending[canonical]; delete pending[canonical];
      invalid.forEach(function (callback) {
        fail(callback, 'Asura public series alias unavailable');
      });
      return;
    }
    request(target,'text/html', function (resp) {
      if (resp.__sourceError) {
        var callbacks=pending[canonical];delete pending[canonical];
        callbacks.forEach(function (callback) {callback(resp);});return;
      }
      savePublicAlias(canonical, resp.finalURL);
      select(resp.body, {
        details: {selector: '*[props*="title"][props*="description"]'},
        chapters: {selector: '*[props*="chapters"]'}
      }, function (dom) {
        var callbacks=pending[canonical];delete pending[canonical];
        if (!dom.__sourceError) {
          cache[canonical]=dom;cachedAt[canonical]=Date.now();
        }
        callbacks.forEach(function (callback) {callback(dom);});
      });
    });
  }
  function seriesMethod(method, id, done) {
    var url = seriesURL(id);
    if (!url) {fail(done,'Invalid Asura series URL');return;}
    seriesData(url,function (result) {
      if (result.__sourceError) {done(result);return;}
      try {
        if (method === 'details') {
          var details = detailsInfo(findAstro(result,'details'),url);
          details.url = publicAlias(url) || url;
          done(details);
        } else {
          var chapterProp = findAstro(result,'chapters');
          var output = chapterList(chapterProp,url);
          if (!output.length) {fail(done,'No public chapters available');return;}
          done(output);
        }
      } catch (e) {fail(done,e);}
    });
  }
  function searchList(page, text, sort, done, rawFilters) {
    if (typeof text !== 'string' || text.length > 200) {
      fail(done,'Invalid search query');return;
    }
    var p = parseNumber(page,1,10000);
    if (p === null || Math.floor(p) !== p) {
      fail(done,'Invalid page number');return;
    }
    var allowedSort = ['popular','latest','rating','title','update'];
    if (allowedSort.indexOf(sort) < 0) {
      fail(done,'Invalid Asura sort');return;
    }
    var query = api + '/series?offset=' + ((p-1)*PER_PAGE) +
      '&limit=' + PER_PAGE + '&sort=' + encodeURIComponent(sort) + '&order=desc';
    if (text.trim()) query += '&search=' + encodeURIComponent(text.trim());
    // The pilot initially accepts only the existing empty filter list.
    // Advanced genres need live metadata from /browse before publication.
    if (rawFilters && (Object.prototype.toString.call(rawFilters) !== '[object Array]' ||
        rawFilters.length)) {fail(done,'Asura advanced filters not available in pilot');return;}
    request(query, 'application/json', function (resp) {
      if (resp.__sourceError) {done(resp);return;}
      var json=parseJSON(resp.body,done);
      if (!json) return;
      if (!json || Object.prototype.toString.call(json.data) !== '[object Array]') {
        fail(done,'Asura API returned no series array');return;
      }
      var seen = {},items = [],missingMediaHosts=[];
      for(var i=0;i<json.data.length;i++) {
        var m=json.data[i];
        if (!m || typeof m.title!=='string' || !m.title.trim()) continue;
        var publicURL = publicSeriesURL(m.public_url);
        var canonical = stableSeriesURL(m.slug);
        if (!publicURL || !canonical || seen[canonical]) continue;
        savePublicAlias(canonical, publicURL);
        seen[canonical] = true;
        var cover=safeImage(m.cover || m.coverUrl);
        if(cover.host && !cover.url && missingMediaHosts.indexOf(cover.host)<0 &&
            missingMediaHosts.length < 3) missingMediaHosts.push(cover.host);
        items.push({id: canonical,title:m.title.trim(),cover:cover.url,url:publicURL});
      }
      if (json.data.length && !items.length) {
        fail(done,'Asura API did not contain compatible series URLs');return;
      }
      done({items:items,hasNextPage:!!(json.meta && json.meta.has_more===true)});
    });
  }
  function pages(chapterId,done) {
    var url=publicChapterURL(chapterId);
    if(!url){fail(done,'Invalid Asura chapter URL');return;}
    request(url,'text/html',function(resp) {
      if(resp.__sourceError){done(resp);return;}
      select(resp.body,{pages:{selector:'*[props*="pages"]'}},function(dom){
        if(dom.__sourceError){done(dom);return;}
        try {
          var result=findAstro(dom,'pages');
          if(!result || Object.prototype.toString.call(result.pages)!=='[object Array]') {
            fail(done,'Asura public page data unavailable (premium/login not accessed)');return;
          }
          if(!result.pages.length){
            fail(done,'Asura chapter has no publicly accessible pages');return;
          }
          var output=[], blocked=[];
          for(var i=0;i<result.pages.length;i++){
            var page=result.pages[i];
            if(!page || typeof page.url!=='string') {
              fail(done,'Invalid Asura public page record');return;
            }
            if (page.tiles !== undefined && page.tiles !== null &&
                (Object.prototype.toString.call(page.tiles) !== '[object Array]' ||
                page.tiles.length > 0)) {
              // Never deliver scrambled or ambiguously parsed image tiles
              // as if readable or downloadable.
              // Processing the documented tile permutation needs a separate,
              // bounded native CoreGraphics implementation and fixture QA.
              fail(done,'Asura chapter uses tiled images; native unscrambling not yet implemented');return;
            }
            var image=safeImage(page.url);
            if(!image.url){
              var host=image.host;
              if(host && blocked.indexOf(host)<0 && blocked.length<3)blocked.push(host);
            } else {
              output.push({index:i,imageUrl:image.url,headers:{Referer:site+'/'}});
            }
          }
          if(output.length!==result.pages.length) {
            fail(done,'Asura image CDN requires review. Blocked hostnames: '+
              blocked.join(', ')+'. No images were requested.');return;
          }
          done(output);
        } catch(e){fail(done,e);}
      });
    });
  }
  this.source={
    metadata:function(){return {
      id:sourceID,name:'Asura Scans EN (experimental)',lang:'en',version:version
    };},
    popular:function(page,done){searchList(page,'','popular',done,[]);},
    search:function(query,page,filters,done){
      searchList(page,query || '',query ? 'latest':'popular',done,filters);
    },
    browseCategories:function(){return [
      {id:'popular',title:'Populares',kind:'ranking'},
      {id:'latest',title:'Recentes',kind:'latest'}
    ];},
    browse:function(category,page,done){
      if(category==='popular')searchList(page,'','popular',done,[]);
      else if(category==='latest')searchList(page,'','latest',done,[]);
      else fail(done,'Unknown Asura category');
    },
    details:function(id,done){seriesMethod('details',id,done);},
    chapters:function(id,done){seriesMethod('chapters',id,done);},
    pages:pages
  };
}).call(this);
