// MangaReader12 source API v1 — MangaDex public API pilot.
// Uses callback-based native HTTPS requests. No authentication, scraping,
// captcha bypass or Android-extension execution.
(function () {
  'use strict';
  var api = 'https://api.mangadex.org';
  var userAgent = 'MangaReader12/0.1 (iOS 12+; github.com/AugustoArbulu/MangaReader12)';

  function fail(done, message) {
    done({ __sourceError: String(message || 'MangaDex request failed') });
  }

  function request(path, done) {
    var req = { method: 'GET', url: api + path, headers: {
      'Accept': 'application/json', 'User-Agent': userAgent
    }};
    Native.httpRequest(JSON.stringify(req), function (raw) {
      try {
        var response = JSON.parse(raw);
        if (!response.ok || response.status < 200 || response.status >= 300) {
          fail(done, response.error || ('MangaDex HTTP ' + response.status +
            (response.status === 429 ? ' (limite de requisições; tente mais tarde)' : '')));
          return;
        }
        var json = JSON.parse(response.body || '{}');
        if (json.result === 'error') {
          fail(done, json.errors && json.errors[0] && json.errors[0].detail || 'Resposta de erro');
          return;
        }
        done(json);
      } catch (error) { fail(done, error.message || error); }
    });
  }

  function text(value) {
    if (typeof value === 'string') return value;
    return '';
  }

  function localized(value) {
    if (typeof value === 'string') return value;
    if (!value || typeof value !== 'object') return '';
    return text(value.en) || text(value['pt-br']) || text(value.ja) ||
      text(value['ja-ro']) || text(value.ko) || text(value['zh-hans']) ||
      text(value[Object.keys(value)[0]]) || '';
  }

  function relationshipsOf(item, kind) {
    return (item.relationships || []).filter(function (rel) { return rel.type === kind; });
  }

  function coverFor(item) {
    var covers = relationshipsOf(item, 'cover_art');
    if (!covers.length || !covers[0].attributes || !covers[0].attributes.fileName) return null;
    return 'https://uploads.mangadex.org/covers/' + encodeURIComponent(item.id) + '/' +
      encodeURIComponent(covers[0].attributes.fileName) + '.256.jpg';
  }

  function asSummary(item) {
    var a = item.attributes || {};
    return {
      id: item.id,
      title: localized(a.title) || 'Sem título',
      cover: coverFor(item),
      url: 'https://mangadex.org/title/' + encodeURIComponent(item.id)
    };
  }

  function listing(path, page, done) {
    var limit = 20;
    var offset = (Math.max(1, Math.min(500, Number(page) || 1)) - 1) * limit;
    // API has a 10,000 result window limit; keep requests bounded.
    path += (path.indexOf('?') < 0 ? '?' : '&') +
      'limit=' + limit + '&offset=' + offset + '&includes%5B%5D=cover_art' +
      '&contentRating%5B%5D=safe&contentRating%5B%5D=suggestive';
    request(path, function (response) {
      if (response.__sourceError) { done(response); return; }
      var items = (response.data || []).map(asSummary);
      var total = Number(response.total || 0);
      done({ items: items, hasNextPage: offset + items.length < total && items.length > 0 });
    });
  }

  var source = {
    metadata: function () {
      return { id: 'org.mangareader12.mangadex', name: 'MangaDex (experimental)', lang: 'en', version: '0.1.0' };
    },

    popular: function (page, done) {
      listing('/manga?order%5BfollowedCount%5D=desc', page, done);
    },

    search: function (query, page, filters, done) {
      listing('/manga?title=' + encodeURIComponent(String(query || '')), page, done);
    },

    details: function (mangaId, done) {
      request('/manga/' + encodeURIComponent(mangaId) + '?includes%5B%5D=cover_art' +
        '&includes%5B%5D=author&includes%5B%5D=artist', function (response) {
        if (response.__sourceError) { done(response); return; }
        var item = response.data || {};
        var a = item.attributes || {};
        var authors = relationshipsOf(item, 'author');
        var artists = relationshipsOf(item, 'artist');
        var tags = a.tags || [];
        var statuses = { ongoing: 'ongoing', completed: 'completed', hiatus: 'hiatus', cancelled: 'cancelled' };
        done({
          id: item.id || mangaId,
          title: localized(a.title) || 'Sem título',
          altTitles: (a.altTitles || []).map(localized).filter(Boolean),
          cover: coverFor(item),
          author: authors.map(function (x) { return x.attributes && x.attributes.name; }).filter(Boolean).join(', ') || null,
          artist: artists.map(function (x) { return x.attributes && x.attributes.name; }).filter(Boolean).join(', ') || null,
          description: (localized(a.description) || '') + '\n\nFonte: MangaDex. Grupos de tradução creditados em cada capítulo.',
          status: statuses[a.status] || 'unknown',
          genres: tags.map(function (tag) { return localized(tag.attributes && tag.attributes.name); }).filter(Boolean),
          url: 'https://mangadex.org/title/' + encodeURIComponent(mangaId)
        });
      });
    },

    chapters: function (mangaId, done) {
      // Pilot loads the newest 100 English chapters. Other languages and
      // older pages require a dedicated follow-on pagination milestone.
      request('/manga/' + encodeURIComponent(mangaId) + '/feed?limit=100&offset=0' +
        '&translatedLanguage%5B%5D=en&includes%5B%5D=scanlation_group' +
        '&order%5Bchapter%5D=desc', function (response) {
        if (response.__sourceError) { done(response); return; }
        done((response.data || []).map(function (item) {
          var a = item.attributes || {};
          var groups = relationshipsOf(item, 'scanlation_group').map(function (rel) {
            return rel.attributes && rel.attributes.name;
          }).filter(Boolean);
          var n = Number(a.chapter), v = Number(a.volume);
          return {
            id: item.id,
            name: text(a.title) || ('Capítulo ' + (a.chapter || '?')),
            number: a.chapter && isFinite(n) ? n : null,
            volume: a.volume && isFinite(v) ? v : null,
            date: a.publishAt ? String(a.publishAt).slice(0, 10) : null,
            scanlator: 'MangaDex • ' + (groups.join(', ') || 'Grupo não informado'),
            language: a.translatedLanguage || 'en',
            url: 'https://mangadex.org/chapter/' + encodeURIComponent(item.id)
          };
        }));
      });
    },

    pages: function (chapterId, done) {
      request('/at-home/server/' + encodeURIComponent(chapterId), function (response) {
        if (response.__sourceError) { done(response); return; }
        var chapter = response.chapter || {};
        var files = chapter.dataSaver || [];
        var base = text(response.baseUrl).replace(/\/$/, '');
        var hash = text(chapter.hash);
        if (!base || !hash || !files.length || base.indexOf('https://') !== 0) {
          fail(done, 'MangaDex não retornou imagens utilizáveis para este capítulo.');
          return;
        }
        done(files.map(function (fileName, index) {
          return {
            index: index,
            imageUrl: base + '/data-saver/' + encodeURIComponent(hash) + '/' + encodeURIComponent(fileName),
            headers: { 'User-Agent': userAgent }
          };
        }));
      });
    }
  };

  // JavaScriptCore expects a global `source` binding.
  this.source = source;
}).call(this);
