// WeebCentral EN candidate for MangaReader12 Source API v1.
// Based on Keiyoushi WeebCentral.kt / Filters.kt (Apache-2.0).
// Offline-contract pilot: not confirmed against the live website or iOS 12.5.8.
// No Android code, auth, WAF automation, injected site scripts, or protected paths.
(function () {
  'use strict';

  var base = 'https://weebcentral.com';
  var sourceId = 'kei.weebcentral.en';
  var version = '0.1.2';
  var FETCH_LIMIT = 32;
  var hostRE = /^https:\/\/(?:www\.)?weebcentral\.com(?=\/|[?#]|$)/i;
  var imageHostRE = /^https:\/\/(?:[a-z0-9-]+\.)*weebcentral\.com(?=\/|[?#]|$)/i;
  var seriesRE = /^https:\/\/(?:www\.)?weebcentral\.com\/series\/([^\/?#]+)(?:\/[^\/?#]+)?\/?(?:[?#].*)?$/i;
  var chapterRE = /^https:\/\/(?:www\.)?weebcentral\.com\/(?:chapters?\/[^?#]+|series\/[^?#]+\/chapter\/[^?#]+)(?:[?#].*)?$/i;

  function fail(done, message) {
    done({__sourceError: String(message && message.message || message || 'WeebCentral error')});
  }
  function request(url, done) {
    if (!hostRE.test(url)) { fail(done, 'Request is outside WeebCentral HTTPS origin'); return; }
    Native.httpRequest(JSON.stringify({
      method: 'GET', url: url, headers: {Accept: 'text/html'}
    }), function (raw) {
      try {
        var data = JSON.parse(raw);
        if (!data.ok || data.status < 200 || data.status >= 300) {
          fail(done, data.error || ('WeebCentral HTTP ' + data.status)); return;
        }
        var finalURL = data.finalURL || url;
        if (!hostRE.test(finalURL)) {
          fail(done, 'Redirect left the permitted WeebCentral host'); return;
        }
        done({body: data.body || '', finalURL: finalURL});
      } catch (e) { fail(done, 'Invalid HTTP response'); }
    });
  }
  function select(html, spec, done) {
    Native.htmlSelect(html, JSON.stringify(spec), function (raw) {
      try {
        var result = JSON.parse(raw);
        if (result.error) { fail(done, result.error); return; }
        done(result.results || {});
      } catch (e) { fail(done, 'Invalid HTML selector response'); }
    });
  }
  function entries(result, key) { return result && result[key] || []; }
  function fld(item, name) { return item && item.fields && item.fields[name] || null; }
  function txt(item) { return item && item.text ? String(item.text).trim() : ''; }
  function attr(item, name) { return item && item.attrs && item.attrs[name] || ''; }
  function resolve(baseURL, part) {
    if (typeof part !== 'string' || !part || /[\u0000-\u001f\u007f]/.test(part)) return null;
    var out = Native.resolveUrl(baseURL, part);
    return typeof out === 'string' && /^https:\/\//i.test(out) ? out : null;
  }
  function siteURL(part) {
    var url = resolve(base + '/', part);
    return url && hostRE.test(url) ? url : null;
  }
  function seriesURL(part) {
    var url = siteURL(part);
    return url && seriesRE.test(url) ? url.replace(/[?#].*$/, '').replace(/\/$/, '') : null;
  }
  function chapterURL(part) {
    var url = siteURL(part);
    return url && chapterRE.test(url) ? url.replace(/[?#].*$/, '').replace(/\/$/, '') : null;
  }
  // Only hostnames (not full URLs or tokens) are retained for diagnostics.
  // Do not fetch media from unknown CDN origins without a manifest review.
  function hostname(url) {
    var m = /^https:\/\/([a-z0-9-]+(?:\.[a-z0-9-]+)*)(?=\/|[?#]|$)/i.exec(url || '');
    return m ? m[1].toLowerCase() : null;
  }
  function firstSrcset(value) {
    return String(value || '').split(',')[0].trim().split(/\s+/)[0];
  }
  function imageChoice(baseURL, candidates) {
    // Prefer explicit lazy image attributes. An external actual image must
    // not silently fall back to a same-origin placeholder in the src attribute.
    for (var i = 0; i < candidates.length; i++) {
      var raw = String(candidates[i] || '').trim();
      if (!raw || /^data:|^blob:/i.test(raw)) continue;
      var url = resolve(baseURL, raw);
      if (!url) continue;
      var host = hostname(url);
      if (!host) continue;
      return {url: imageHostRE.test(url) ? url : null, host: host};
    }
    return {url: null, host: null};
  }
  function coverInfo(baseURL, parent) {
    if (!parent) return {url: null, host: null};
    return imageChoice(baseURL, [
      firstSrcset(attr(fld(parent, 'source'), 'srcset')),
      attr(fld(parent, 'image'), 'data-src'),
      attr(fld(parent, 'image'), 'data-original'),
      attr(fld(parent, 'image'), 'data-lazy-src'),
      firstSrcset(attr(fld(parent, 'image'), 'srcset')),
      attr(fld(parent, 'image'), 'src'),
      attr(parent, 'src')
    ]);
  }
  function coverDiagnostic(info) {
    // The app already supports this optional field on list cards.
    return {
      matched: true,
      coverFound: !!info.url,
      fields: ['weebcentral-cover'],
      attributes: info.host ? ['image-hostname'] : [],
      kinds: info.host ? ['image-hostname=' + info.host] : [],
      outputClass: info.url ? 'permitted-https' : (info.host ? 'host-not-allowed' : 'missing'),
      outputLength: info.url ? info.url.length : 0
    };
  }
  function pageNumber(value) {
    var num = Number(value);
    return isFinite(num) && num >= 1 && num <= 10000 && Math.floor(num) === num
      ? num : 1;
  }
  function listing(page, searchText, sort, done) {
    var q = searchText == null ? '' : String(searchText);
    var query = '/search/data?text=' + encodeURIComponent(q.replace(/[!#:(),-]/g, ' ').trim()) +
      '&sort=' + encodeURIComponent(sort) +
      '&order=Descending&limit=' + FETCH_LIMIT +
      '&offset=' + ((pageNumber(page) - 1) * FETCH_LIMIT) +
      '&display_mode=' + encodeURIComponent('Full Display');
    request(base + query, function (resp) {
      if (resp.__sourceError) { done(resp); return; }
      select(resp.body, {
        items: {selector: 'article > section > a', fields: {
          title: 'div:not([class]):last-child',
          source: 'source',
          image: 'img'
        }},
        next: {selector: 'button'}
      }, function (dom) {
        if (dom.__sourceError) { done(dom); return; }
        var found = entries(dom, 'items'), seen = {}, items = [];
        for (var i = 0; i < found.length; i++) {
          var item = found[i];
          var url = seriesURL(attr(item, 'href'));
          var title = txt(fld(item, 'title'));
          if (!url || !title || seen[url]) continue;
          seen[url] = true;
          var cover = coverInfo(resp.finalURL, item);
          items.push({id: url, title: title, cover: cover.url, url: url,
            coverDiagnostic: coverDiagnostic(cover)});
        }
        // Fail closed on changed templates rather than treating a broken DOM
        // as a legitimately empty catalog.
        if (found.length && !items.length) { fail(done, 'Series card markup changed'); return; }
        if (!found.length && resp.body.length > 1200 && /<article\b/i.test(resp.body)) {
          fail(done, 'Series listing selector found no items'); return;
        }
        done({items: items, hasNextPage: entries(dom, 'next').length > 0});
      });
    });
  }
  function detailsHTML(mangaId, done) {
    var url = seriesURL(mangaId);
    if (!url) { fail(done, 'Invalid WeebCentral series URL'); return; }
    request(url, done);
  }
  function parseInfoRow(row, map) {
    var value = txt(row).replace(/\s+/g, ' ').trim();
    var match = /^(Author|Artist|Tag|Type|Status|Description|Associated Name|Associated Names)\s*:\s*(.*)$/i.exec(value);
    if (!match) return;
    var key = match[1].toLowerCase(), body = match[2];
    if (key === 'author') map.author = body;
    if (key === 'artist') map.artist = body;
    if (key === 'status') map.status = body;
    if (key === 'description') map.description = body;
    if (key === 'associated name' || key === 'associated names') map.alt = body;
    if (key === 'tag' || key === 'type') {
      if (body) map.genres.push(body);
    }
  }
  function getDetails(mangaId, done) {
    detailsHTML(mangaId, function (resp) {
      if (resp.__sourceError) { done(resp); return; }
      select(resp.body, {
        title: {selector: 'section[x-data] h1'},
        rows: {selector: 'section[x-data] ul > li'},
        poster: {selector: 'section[x-data] > section', fields: {
          source: 'source', image: 'img'
        }},
        meta: {selector: 'meta[property="og:image"]'}
      }, function (dom) {
        if (dom.__sourceError) { done(dom); return; }
        var title = txt(entries(dom, 'title')[0]);
        if (!title) { fail(done, 'Series title missing from HTML'); return; }
        var info = {genres: []};
        entries(dom, 'rows').forEach(function (row) { parseInfoRow(row, info); });
        var posterCover = coverInfo(resp.finalURL, entries(dom, 'poster')[0]);
        var metaCover = imageChoice(resp.finalURL, [attr(entries(dom, 'meta')[0], 'content')]);
        var cover = posterCover.url || metaCover.url;
        var status = (info.status || '').toLowerCase();
        done({
          id: seriesURL(mangaId),
          title: title,
          altTitles: info.alt ? [info.alt] : [],
          cover: cover,
          author: info.author || null,
          artist: info.artist || null,
          description: info.description || '',
          status: status === 'ongoing' ? 'ongoing' :
            (status === 'complete' || status === 'completed') ? 'completed' :
            status === 'hiatus' ? 'hiatus' :
            (status === 'canceled' || status === 'cancelled') ? 'cancelled' : 'unknown',
          genres: info.genres,
          url: seriesURL(mangaId)
        });
      });
    });
  }
  function getChapters(mangaId, done) {
    var canonical = seriesURL(mangaId);
    var match = canonical && seriesRE.exec(canonical);
    if (!match) { fail(done, 'Invalid WeebCentral series ID'); return; }
    // Upstream path segments[1] is the stable ID, independent of the slug.
    var url = base + '/series/' + encodeURIComponent(match[1]) + '/full-chapter-list';
    request(url, function (resp) {
      if (resp.__sourceError) { done(resp); return; }
      select(resp.body, {
        chapters: {selector: 'div[x-data] > a', fields: {
          name: 'span.flex > span', date: 'time[datetime]', official: 'img'
        }}
      }, function (dom) {
        if (dom.__sourceError) { done(dom); return; }
        var found = entries(dom, 'chapters'), chapters = [], seen = {};
        for (var i = 0; i < found.length; i++) {
          var raw = found[i], path = chapterURL(attr(raw, 'href'));
          if (!path || seen[path]) continue;
          seen[path] = true;
          var name = txt(fld(raw, 'name')) || 'Chapter ' + (found.length - i);
          var numberMatch = /(?:chapter|ch\.?)\s*([0-9]+(?:\.[0-9]+)?)/i.exec(name);
          var official = /official/i.test(attr(fld(raw, 'official'), 'src'));
          chapters.push({
            id: path,
            name: name,
            number: numberMatch ? Number(numberMatch[1]) : null,
            volume: null, date: null,
            scanlator: official ? 'Official' : null,
            language: 'en', url: path
          });
        }
        if (!chapters.length) { fail(done, 'No compatible chapter links found'); return; }
        done(chapters.reverse());
      });
    });
  }
  function getPages(chapterId, done) {
    var url = chapterURL(chapterId);
    if (!url) { fail(done, 'Invalid WeebCentral chapter URL'); return; }
    var imageList = url + '/images?is_prev=False&reading_style=long_strip';
    request(imageList, function (resp) {
      if (resp.__sourceError) { done(resp); return; }
      // Jsoup [attr~=regex] is NOT CSS [attr~=word]. For WebKit's
      // querySelectorAll use the CSS substring operator [attr*="..."].
      // Count nearby inert DOM elements for a zero-match diagnostic only.
      select(resp.body, {
        images: {selector: 'section[x-data*="scroll"] > img'},
        scrollSections: {selector: 'section[x-data*="scroll"]'},
        nestedImages: {selector: 'section[x-data*="scroll"] img'},
        allImages: {selector: 'img[src], img[data-src], img[data-original]'}
      }, function (dom) {
        if (dom.__sourceError) { done(dom); return; }
        var found = entries(dom, 'images'), pages = [], deniedHosts = [];
        var missingCount = 0;
        for (var i = 0; i < found.length; i++) {
          var el = found[i];
          var image = imageChoice(resp.finalURL, [
            attr(el, 'data-src'), attr(el, 'data-original'),
            attr(el, 'data-lazy-src'), firstSrcset(attr(el, 'srcset')),
            attr(el, 'src')
          ]);
          if (!image.url) {
            if (image.host && deniedHosts.indexOf(image.host) < 0 &&
                deniedHosts.length < 3) deniedHosts.push(image.host);
            if (!image.host) missingCount++;
          } else {
            pages.push({index: pages.length, imageUrl: image.url,
              headers: {Referer: base + '/'}});
          }
        }
        // Never deliver an incomplete chapter when any page was skipped.
        if (!found.length) {
          fail(done, 'WeebCentral: no direct chapter images found (WebKit CSS).' +
            ' scroll sections=' + entries(dom, 'scrollSections').length +
            ', nested images=' + entries(dom, 'nestedImages').length +
            ', document images=' + entries(dom, 'allImages').length +
            '. No extra requests were made; selectors or HTML may have changed.'); return;
        }
        if (deniedHosts.length || missingCount || pages.length !== found.length) {
          var reason = deniedHosts.length ?
            'Blocked image hostnames: ' + deniedHosts.join(', ') + '.' :
            'No usable HTTPS image URL in chapter image attributes.';
          fail(done, 'WeebCentral: ' + reason + ' Images parsed: ' + found.length +
            ', permitted: ' + pages.length + ', missing/unsupported: ' + missingCount +
            '. Only hostnames are reported; no blocked images were downloaded.');
          return;
        }
        done(pages);
      });
    });
  }
  var source = {
    metadata: function () {
      return {id: sourceId, name: 'WeebCentral EN (experimental)', lang: 'en', version: version};
    },
    popular: function (page, done) { listing(page, '', 'Popularity', done); },
    search: function (query, page, filters, done) {
      listing(page, query, query && String(query).trim() ? 'Best Match' : 'Popularity', done);
    },
    browseCategories: function () {
      return [
        {id: 'popular', title: 'Populares', kind: 'ranking'},
        {id: 'latest', title: 'Recentes', kind: 'latest'}
      ];
    },
    browse: function (mode, page, done) {
      if (mode === 'popular') listing(page, '', 'Popularity', done);
      else if (mode === 'latest') listing(page, '', 'Latest Updates', done);
      else fail(done, 'Unsupported discovery category');
    },
    details: getDetails,
    chapters: getChapters,
    pages: getPages
  };
  this.source = source;
}).call(this);
