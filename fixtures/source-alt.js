var source = {
  metadata: function() {
    return {
      id: "fixture.altdemo",
      name: "MangaReader12 Alt Demo",
      lang: "en",
      version: "1.0.1"
    };
  },

  popular: function(page) {
    return {
      items: [
        {
          id: "alt-demo-1",
          title: "Demo Manga",
          cover: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page2.png",
          url: "https://example.org/manga/alt-demo-1"
        }
      ],
      hasNextPage: false
    };
  },

  search: function(query, page, filters) {
    return {
      items: [
        {
          id: "alt-demo-1",
          title: "Demo Manga",
          cover: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page2.png",
          url: "https://example.org/manga/alt-demo-1"
        }
      ],
      hasNextPage: false
    };
  },

  details: function(mangaId) {
    return {
      id: mangaId,
      title: "Demo Manga",
      altTitles: ["MangaReader12 Migration Target"],
      cover: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page2.png",
      author: "MangaReader12 Alt",
      artist: "MangaReader12 Alt",
      description: "Controlled alternate source used to validate source migration.",
      status: "ongoing",
      genres: ["Demo", "Migration"],
      url: "https://example.org/manga/" + mangaId
    };
  },

  chapters: function(mangaId) {
    return [
      {
        id: "alt-c2",
        name: "Chapter 2",
        number: 2,
        volume: 1,
        date: "2026-10-29",
        scanlator: "MangaReader12 Alt",
        language: "en",
        url: "https://example.org/chapter/alt-c2"
      },
      {
        id: "alt-c1",
        name: "Chapter 1",
        number: 1,
        volume: 1,
        date: "2026-10-29",
        scanlator: "MangaReader12 Alt",
        language: "en",
        url: "https://example.org/chapter/alt-c1"
      }
    ];
  },

  pages: function(chapterId) {
    return [
      {
        index: 0,
        imageUrl: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page2.png",
        headers: {}
      },
      {
        index: 1,
        imageUrl: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page1.png",
        headers: {}
      }
    ];
  }
};
