from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from home.tests import make_user

# The documents the privacy policy and terms of use pages link to
# (static/documents, made from the Word files in local_documents)
DOCUMENTS = settings.BASE_DIR / "static" / "documents"


class LegalDocumentTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("Aino", "Mäkinen"))

    def test_pages_link_their_documents(self):
        for page, document in (("privacy-policy", "lut_kyyti_privacy_policy.pdf"), ("terms-of-use", "lut_kyyti_terms_of_use.pdf")):
            response = self.client.get(reverse(page))
            self.assertContains(response, f"documents/{document}")
            self.assertContains(response, "Last updated: October 2026")

    def test_the_documents_are_two_different_pdfs(self):
        privacy = (DOCUMENTS / "lut_kyyti_privacy_policy.pdf").read_bytes()
        terms = (DOCUMENTS / "lut_kyyti_terms_of_use.pdf").read_bytes()
        self.assertTrue(privacy.startswith(b"%PDF") and terms.startswith(b"%PDF"))
        # Both links once served the same unrelated file
        self.assertNotEqual(privacy, terms)


class OfflinePageTests(TestCase):
    """The page the service worker shows without a connection (templates/offline.html)."""

    def test_it_is_the_apps_own_page(self):
        page = self.client.get(reverse("offline"))
        self.assertContains(page, "You are offline")
        self.assertContains(page, "LUT Kyyti")
        self.assertNotContains(page, "Default offline template")

    def test_it_is_translated(self):
        page = self.client.get(reverse("offline"), HTTP_ACCEPT_LANGUAGE="fi")
        self.assertContains(page, "Ei internetyhteyttä")
