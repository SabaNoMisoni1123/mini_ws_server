import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from mini_ws_server.repositories.firestore import FirestoreRepository  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "firebase_admin":
        raise
    FirestoreRepository = None


@unittest.skipIf(FirestoreRepository is None, "firebase_admin is not installed")
class FirestoreRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.repository = FirestoreRepository.__new__(FirestoreRepository)
        self.repository.db = Mock()

    @patch("mini_ws_server.repositories.firestore.firestore.client")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.initialize_app")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.get_app")
    def test_init_uses_application_default_credentials(
        self, get_app, initialize_app, firestore_client
    ):
        get_app.side_effect = ValueError

        repository = FirestoreRepository()

        initialize_app.assert_called_once_with()
        self.assertIs(repository.db, firestore_client.return_value)

    @patch("mini_ws_server.repositories.firestore.firestore.client")
    @patch("mini_ws_server.repositories.firestore.credentials.Certificate")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.initialize_app")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.get_app")
    def test_init_keeps_explicit_credential_path_support(
        self, get_app, initialize_app, certificate, firestore_client
    ):
        get_app.side_effect = ValueError

        FirestoreRepository("credentials/firebase.json")

        expected_path = PROJECT_ROOT / "credentials" / "firebase.json"
        certificate.assert_called_once_with(str(expected_path))
        initialize_app.assert_called_once_with(certificate.return_value)

    @patch("mini_ws_server.repositories.firestore.firestore.client")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.initialize_app")
    @patch("mini_ws_server.repositories.firestore.firebase_admin.get_app")
    def test_init_reuses_existing_firebase_app(
        self, get_app, initialize_app, firestore_client
    ):
        get_app.return_value = object()

        FirestoreRepository()

        initialize_app.assert_not_called()

    def test_list_site_data_keeps_all_data_and_document_reference(self):
        reference = Mock()
        snapshot = SimpleNamespace(
            id="document-id",
            reference=reference,
            to_dict=lambda: {"id": "source", "name": "名称", "extra": True},
        )
        collection = self.repository.db.collection.return_value
        collection.stream.return_value = [snapshot]

        documents = self.repository.list_site_data()

        self.repository.db.collection.assert_called_once_with("siteData")
        self.assertEqual(documents[0].document_id, "document-id")
        self.assertIs(documents[0].reference, reference)
        self.assertEqual(documents[0].data["extra"], True)

    def test_add_update_and_delete_site_data_use_expected_references(self):
        data = {"id": "source", "name": "名称", "url": "https://example.test", "no": 0}
        collection = self.repository.db.collection.return_value
        reference = Mock()

        self.repository.add_site_data(data)
        self.repository.update_site_data(reference, {"name": "新名称", "url": data["url"], "no": 0})
        self.repository.delete_site_data(reference)

        self.repository.db.collection.assert_called_once_with("siteData")
        collection.add.assert_called_once_with(data)
        reference.update.assert_called_once_with(
            {"name": "新名称", "url": "https://example.test", "no": 0}
        )
        reference.delete.assert_called_once_with()

    def test_load_current_hashes_propagates_firestore_failure(self):
        collection = self.repository.db.collection.return_value
        collection.order_by.side_effect = RuntimeError("read failed")

        with self.assertRaisesRegex(RuntimeError, "read failed"):
            self.repository.load_current_hashes("source")


if __name__ == "__main__":
    unittest.main()
