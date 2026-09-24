import io
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import storage
from .ingest import UploadRejected, ingest
from .models import UploadedDocument

TEST_KEY = "0nFGnZBUe0V1e8Qk3S0mFvhk4E9O3q0l7wD1mYv5dAc="


def png_bytes():
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 30, 30)).save(out, format="PNG")
    return out.getvalue()


def pdf_bytes(text="Hemoglobin A1c 7.2 percent"):
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class StorageTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(
            PRIVATE_MEDIA_ROOT=__import__("pathlib").Path(self.tmp),
            DOCUMENT_STORAGE="local",
            DOCUMENT_ENCRYPTION_KEY=TEST_KEY,
        )
        self.override.enable()
        User = get_user_model()
        self.user = User.objects.create_user("pat", "pat@example.com", "Passw0rd!xy")
        self.other = User.objects.create_user("sam", "sam@example.com", "Passw0rd!xy")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)


class EncryptedStorageTests(StorageTestCase):
    def test_files_are_encrypted_at_rest_and_round_trip(self):
        data = pdf_bytes()
        ref = storage.save(data)
        on_disk = (storage.settings.PRIVATE_MEDIA_ROOT / ref).read_bytes()
        self.assertNotIn(b"%PDF", on_disk)
        self.assertEqual(storage.load(ref), data)

    def test_keys_never_contain_the_file_name(self):
        doc = ingest(self.user, SimpleUploadedFile("maria-lab-results.pdf", pdf_bytes(), "application/pdf"))
        self.assertNotIn("maria", doc.file_key)
        self.assertTrue(doc.file_key.endswith(".bin"))

    def test_renamed_files_are_rejected(self):
        with self.assertRaises(UploadRejected):
            ingest(self.user, SimpleUploadedFile("scan.pdf", b"MZ\x90\x00 not a pdf", "application/pdf"))

    def test_pdf_text_is_extracted(self):
        doc = ingest(self.user, SimpleUploadedFile("a1c.pdf", pdf_bytes(), "application/pdf"))
        self.assertIn("A1c 7.2", doc.extracted_text)


class FileAccessTests(StorageTestCase):
    def test_only_the_owner_can_open_a_file(self):
        doc = ingest(self.user, SimpleUploadedFile("photo.png", png_bytes(), "image/png"))
        url = reverse("documents:file", args=[doc.pk])

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.user)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertEqual(r["Cache-Control"], "private, no-store")
        self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_signed_out_visitors_are_sent_to_login(self):
        doc = ingest(self.user, SimpleUploadedFile("photo.png", png_bytes(), "image/png"))
        self.assertEqual(self.client.get(reverse("documents:file", args=[doc.pk])).status_code, 302)

    def test_deleting_a_document_removes_the_stored_file(self):
        doc = ingest(self.user, SimpleUploadedFile("photo.png", png_bytes(), "image/png"))
        path = storage.settings.PRIVATE_MEDIA_ROOT / doc.file_key
        self.assertTrue(path.exists())
        self.client.force_login(self.user)
        self.client.post(reverse("documents:delete", args=[doc.pk]))
        self.assertFalse(path.exists())


class IcebergBackendTests(StorageTestCase):
    @override_settings(DOCUMENT_STORAGE="iceberg", ICEBERG_TOKEN="kic_test")
    def test_upload_sends_ciphertext_through_the_three_step_flow(self):
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(("POST", url, json))
            res = mock.MagicMock(status_code=200)
            res.json.return_value = {"upload_url": "https://r2.example/put", "delivery_url": "https://cdn.katalyst-crm.com/a/abc"}
            return res

        def fake_put(url, data=None, headers=None, timeout=None):
            calls.append(("PUT", url, data))
            return mock.MagicMock(status_code=200)

        with mock.patch("documents.storage.requests.post", fake_post), \
             mock.patch("documents.storage.requests.put", fake_put):
            ref = storage.save(b"%PDF-1.4 secret lab")

        self.assertEqual(calls[0][1], "https://dashboard.katalyst-crm.com/assets/init-upload")
        self.assertEqual(calls[0][2]["content_type"], "application/octet-stream")
        self.assertEqual(calls[1][0], "PUT")
        self.assertNotIn(b"secret lab", calls[1][2])  # only ciphertext leaves the app
        self.assertEqual(calls[2][1], "https://dashboard.katalyst-crm.com/assets/complete")
        self.assertTrue(ref.endswith("|https://cdn.katalyst-crm.com/a/abc"))

        uploaded = calls[1][2]
        with mock.patch("documents.storage.requests.get",
                        return_value=mock.MagicMock(status_code=200, content=uploaded)):
            self.assertEqual(storage.load(ref), b"%PDF-1.4 secret lab")
