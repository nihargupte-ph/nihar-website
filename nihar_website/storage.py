from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Content-hashed static filenames, so nginx's `Cache-Control: public, immutable` is honest.

    /static/ is served with a 30-day (90 for svg) immutable expiry behind Cloudflare. Under plain
    StaticFilesStorage the URL never changes, so an edited file stays pinned in every browser that
    has already loaded it — a fix cannot reach a phone until the month is out. Hashing the name
    makes each new version a new URL, which the un-cached HTML points at straight away.

    `manifest_strict = False` because two things legitimately have no manifest entry: `deck_static`
    in presentations/render.py is a *directory* prefix, and deck assets under it are located by
    DeckStaticFinder and named only inside deck templates. Both fall back to the unhashed URL,
    which is what they were getting before.
    """

    manifest_strict = False

    def stored_name(self, name):
        """A name that is neither in the manifest nor on disk gets its unhashed URL, not a 500.

        With `manifest_strict = False` Django still opens the file to hash it, and raises
        ValueError if it is missing — which took down /mindmap/physics/ over an index JSON that
        has not been generated yet. The browser gets a 404 for that one asset instead.
        """
        try:
            return super().stored_name(name)
        except ValueError:
            return name

    def post_process(self, paths, dry_run=False, **options):
        """Never fail a deploy over a reference we cannot rewrite.

        The vendored theme in static/assets/css/main.css points at images it never shipped
        (`images/overlay.png`), and Django's default is to abort collectstatic for the whole
        project. Such a file is left exactly as it is — unhashed, and no worse than before.
        """
        for name, hashed_name, processed in super().post_process(paths, dry_run, **options):
            if isinstance(processed, Exception):
                self.stderr_note(name, processed)
                yield name, hashed_name, False
            else:
                yield name, hashed_name, processed

    def stderr_note(self, name, exc):
        import sys
        print(f'  (left {name} unhashed: {exc})', file=sys.stderr)
