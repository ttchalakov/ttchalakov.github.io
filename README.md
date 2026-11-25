# ttchalakov.github.io

Source for my research website, **https://ttchalakov.github.io**. It is built with the [al-folio](https://github.com/alshedivat/al-folio) Jekyll template (v1.2, from upstream commit [`fde4cbf`](https://github.com/alshedivat/al-folio/tree/fde4cbfa59a8dd5efe0cba90ddf62ebab1fad7f1)) and hosted on GitHub Pages.

## Where things live

| To change                                  | Edit                                                                                                                                                                                                      |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Name, site description, URL, feature flags | `_config.yml`                                                                                                                                                                                             |
| Home page bio and subtitle                 | `_pages/about.md` (photo: `assets/img/profile/prof_pic.webp`; see [Profile photo](#profile-photo))                                                                                                        |
| Publications                               | `_bibliography/papers.bib` (the home page lists every `@article` and `@inproceedings` entry, after any `@unpublished` papers under review; `@techreport` entries are listed separately as working papers) |
| Projects                                   | one Markdown file per project in `_projects/`, media in `assets/img/projects/<project>/`                                                                                                                  |
| Contact and profile icons                  | `_data/socials.yml`                                                                                                                                                                                       |
| Navbar pages and their order               | `nav` and `nav_order` in each file in `_pages/`                                                                                                                                                           |
| Accent color (links, headings, badges)     | `$purple-color` (light theme) and `$cyan-color` (dark theme) in `assets/css/main.scss`                                                                                                                    |
| Which crawlers may visit                   | `robots.txt` (AI-training crawlers are blocked; refresh the list from [ai.robots.txt](https://github.com/ai-robots-txt/ai.robots.txt) now and then)                                                       |

Layouts, styles, and scripts come from versioned `al_*` gems pinned in the `Gemfile`, so this repo holds only configuration and content. Two pages exist but are hidden from the navbar until there is something to show: `/blog/` and `/repositories/` (set `nav: true` in their file in `_pages/`). There is no CV page on purpose: the home page's Background list covers it, and a full CV is sent on request.

## Preview locally

One-time setup: `brew install ruby@3.3 imagemagick`. Homebrew's Ruby is installed alongside the macOS system Ruby and does not replace it. Then:

```bash
./start.sh   # turns on http://localhost:4000 in the background; pages rebuild when you save
./stop.sh    # turns it off
```

`./start.sh --open` also opens the site in your browser. The first run installs the gems into `vendor/bundle`. Server output, including build errors, goes to `tmp/server.log`. Restart (`./stop.sh && ./start.sh`) after editing `_config.yml`, because config changes aren't picked up automatically. ImageMagick is optional: without it, the preview uses the original images instead of the resized WebP copies the live site serves.

With Docker instead: `docker compose up`, then open http://localhost:8080.

## Publishing

Pushing to `main` runs `.github/workflows/deploy.yml`. It builds the site and pushes the result to the `gh-pages` branch, which GitHub Pages serves. Don't edit `gh-pages` by hand.

Publish with `bin/publish.sh "Commit message"`, not a plain `git push`. For privacy, the repository keeps no history: the script replaces `main` with a single commit of the current files and force-pushes it, and the deploy replaces `gh-pages` with a single commit too. So once you remove an email or swap a photo, the old version isn't left in the commit history. This hides old versions from the branch and commit views, but GitHub can still serve an old commit by its ID, and the repository's Activity page lists force pushes. To fully purge something, delete and recreate the repository, or ask GitHub Support.

One-time setup after the first successful run: in **Settings → Pages → Build and deployment**, set **Source** to _Deploy from a branch_, with branch `gh-pages` and folder `/ (root)`.

## Images and videos

- Keep images under about 2000 px wide. The deploy build makes resized WebP copies automatically.
- Use H.264 MP4 for videos stored in the repo, and keep them small (a few MB). Embed longer videos from YouTube or Vimeo.
- `.venv/` (not committed) is a Python environment for scripted image and video work.

To add media to a project page, put the files in `assets/img/projects/<project>/` or `assets/video/`, then include them in the page's Markdown:

```liquid
{% include figure.liquid path="assets/img/projects/<project>/photo.jpg" class="img-fluid rounded z-depth-1" zoomable=true %}
{% include video.liquid path="assets/video/<name>.mp4" class="img-fluid rounded z-depth-1" controls=true %}
```

To show a picture on the project's card, add `img: assets/img/projects/<project>/thumbnail.jpg` to the page's front matter. To show one next to a paper in the publication lists, put it in `assets/img/publication_preview/` and add `preview = {file.png}` to the paper's entry in `_bibliography/papers.bib`. The column is about 240 px wide, so crop to what matters and prefer wide images over tall ones.

## Profile photo

`assets/img/profile/prof_pic.webp` is made from an original photo with `bin/cloak_photo.sh`. Keep originals outside the repo: phone photos carry GPS coordinates, and any file in the repo's top folder gets published (`*.heic` files are gitignored and excluded from the build as a safeguard). To replace the photo:

```bash
bin/cloak_photo.sh ~/Downloads/IMG_1234.HEIC assets/img/profile/prof_pic.webp --no-cloak
```

This converts the photo to sRGB, drops all its metadata (location, date, phone model), crops a 4:5 portrait around the face, and writes a WebP. To frame it differently, use `--face-fraction` or `--crop`. It takes a few minutes, mostly to install PyTorch (used to find the face) into a temporary Python environment, which it deletes when it finishes.

Without `--no-cloak`, the script also adds a cloak against face recognition: a change to the face, computed against four open face-recognition models, that makes it match the original poorly. It then tests the saved file against those four models and three others. The current photo has no cloak. On it, the default strength stopped 6 of the 7 test models from matching, but looked odd up close. Versions too faint to notice stopped none. The research agrees: a cloak strong enough to work shows, and newer models, or ones trained to resist cloaks, see through it anyway.

To try a cloak on a future photo anyway, add `--compare /tmp/check.jpg` and look at that before-and-after image, at page size and up close, before publishing. `--strength low|medium|high` trades protection against visibility. Keep a cloaked photo in WebP: the theme serves WebP as is, while its build re-encodes JPEG and PNG into resized copies, which would weaken the cloak. A cloaked run takes 10 to 15 minutes. It installs its Python packages (about 1 GB) and downloads the models (about 1.5 GB) into temporary folders, and deletes them when it finishes. Building dlib needs CMake; without it, that test is skipped.

## Updating al-folio

Each al-folio release lists new gem versions. Update the pins in the `Gemfile`. Add any new plugin to both the `Gemfile` and the `plugins:` list in `_config.yml`, because a plugin listed in only one of them does nothing. Then run:

```bash
bundle update
bundle exec al-folio upgrade audit
```

`assets/css/main.scss` overrides the gem's copy to set the accent color, bold the whole name, and widen the paper-image column in publication lists. After updating `al_folio_core`, copy the gem's new `assets/css/main.scss` over it and re-add the `$purple-color` and `$cyan-color` lines and the two rules at the end of the file. The two files in `_includes/plugins/` override the gem's image-tools wrappers to add the PhotoSwipe image viewer (zoom and pan for paper images); after an update, check that they still match the gem's versions apart from the added viewer.

Upstream documentation: [customization](https://github.com/alshedivat/al-folio/blob/main/docs/CUSTOMIZE.md), [FAQ](https://github.com/alshedivat/al-folio/blob/main/docs/FAQ.md), [troubleshooting](https://github.com/alshedivat/al-folio/blob/main/docs/TROUBLESHOOTING.md).

## Optional extras (not set up)

These workflows live in upstream's `.github/workflows/` and can be copied in later:

- `update-citations.yml` refreshes Google Scholar citation counts on a schedule. It needs `scholar_userid` in `_data/socials.yml` and upstream's `bin/update_scholar_citations.py`.

## License

The al-folio template code is MIT-licensed; see `LICENSE`.
