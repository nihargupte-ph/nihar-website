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
