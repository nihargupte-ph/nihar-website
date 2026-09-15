from django.test import TestCase


class MindmapViewerIndexTest(TestCase):
    def test_cs_viewer_exposes_index_url(self):
        r = self.client.get("/mindmap/cs/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "data-index-url")
        self.assertContains(r, "cs-stat-index.json")

    def test_physics_viewer_exposes_index_url(self):
        r = self.client.get("/mindmap/physics/")
        self.assertContains(r, "physics-index.json")


class MindmapViewerProductionStorageTest(TestCase):
    """Production hashes static names; a referenced file missing from disk must not 500 the page."""

    def test_physics_viewer_renders_without_its_index_file(self):
        import tempfile
        from django.test import override_settings
        storages = {
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'nihar_website.storage.ForgivingManifestStaticFilesStorage'},
        }
        with tempfile.TemporaryDirectory() as root, override_settings(STORAGES=storages, STATIC_ROOT=root):
            r = self.client.get("/mindmap/physics/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "physics-index.json")
