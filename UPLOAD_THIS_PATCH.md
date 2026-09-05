# Upload instructions

This ZIP contains only files added or changed by Milestone 1A.

On GitHub, open the repository root, choose **Add file → Upload files**, then drag the **contents inside this extracted patch folder** into the upload area.

The upload must preserve these paths, especially:

- `MangaReader12.xcodeproj/project.pbxproj`
- `MangaReader12/Core/...`
- `MangaReader12/Database/...`
- `MangaReader12/Networking/...`
- `MangaReader12/Sources/...`
- `MangaReader12/SourceRuntime/...`

Suggested commit message:

`Milestone 1A - core foundation`

The existing `.github/workflows/build.yml` does not need to be replaced. A push to `main` will start the existing GitHub Actions workflow automatically.
