var source = {
  metadata: function() {
    return {
      id: "fixture.localdemo",
      name: "MangaReader12 Demo",
      lang: "en",
      version: "1.2.0"
    };
  },

  popular: function(page) {
    return {
      items: [
        {
          id: "demo-1",
          title: "Demo Manga",
          cover: null,
          url: "https://example.com/manga/demo-1"
        }
      ],
      hasNextPage: false
    };
  },

  search: function(query, page, filters) {
    return {
      items: [
        {
          id: "demo-1",
          title: "Demo Manga",
          cover: null,
          url: "https://example.com/manga/demo-1"
        }
      ],
      hasNextPage: false
    };
  },

  details: function(mangaId) {
    return {
      id: mangaId,
      title: "Demo Manga",
      altTitles: ["MangaReader12 Fixture"],
      cover: null,
      author: "MangaReader12",
      artist: "MangaReader12",
      description: "Updates + categories + reader settings fixture for iOS 12 validation.",
      status: "ongoing",
      genres: ["Demo", "Reader"],
      url: "https://example.com/manga/" + mangaId
    };
  },

  chapters: function(mangaId) {
    return [
      {
        id: "demo-c2",
        name: "Chapter 2",
        number: 2,
        volume: 1,
        date: "2026-10-29",
        scanlator: "MangaReader12",
        language: "en",
        url: "https://example.com/chapter/demo-c2"
      },
      {
        id: "demo-c1",
        name: "Chapter 1",
        number: 1,
        volume: 1,
        date: "2026-10-29",
        scanlator: "MangaReader12",
        language: "en",
        url: "https://example.com/chapter/demo-c1"
      }
    ];
  },

  pages: function(chapterId) {
    return [
      {
        index: 0,
        imageUrl: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page1.png",
        headers: {}
      },
      {
        index: 1,
        imageUrl: "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/page2.png",
        headers: {}
      }
    ];
  }
};
