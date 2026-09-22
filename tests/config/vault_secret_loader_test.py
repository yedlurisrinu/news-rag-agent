import os
import pytest
from unittest.mock import MagicMock, patch


class TestLoadSecrets:
    def test_raises_when_vault_addr_missing(self, monkeypatch):
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.setenv("VAULT_TOKEN", "token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        from config.vault_secrets import load_secrets

        with pytest.raises(ValueError, match="VAULT_ADDR and VAULT_TOKEN must be set"):
            load_secrets()

    def test_raises_when_vault_token_missing(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        from config.vault_secrets import load_secrets

        with pytest.raises(ValueError, match="VAULT_ADDR and VAULT_TOKEN must be set"):
            load_secrets()

    def test_raises_when_secret_path_missing(self, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "token")
        monkeypatch.delenv("VAULT_SECRET_PATH", raising=False)

        from config.vault_secrets import load_secrets

        with pytest.raises(ValueError, match="VAULT_SECRET_PATH must be set"):
            load_secrets()

    @patch("config.vault_secrets.Client")
    def test_raises_when_authentication_fails(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "bad-token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = False
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        with pytest.raises(ValueError, match="Vault authentication failed"):
            load_secrets()

    @patch("config.vault_secrets.Client")
    def test_loads_single_secret_path(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "valid-token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"DB_HOST": "localhost", "DB_PORT": "5432"}}
        }
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        load_secrets()

        assert os.environ["DB_HOST"] == "localhost"
        assert os.environ["DB_PORT"] == "5432"
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="myapp", mount_point="secret"
        )

    @patch("config.vault_secrets.Client")
    def test_loads_multiple_secret_paths(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "valid-token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp,secret/shared")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.side_effect = [
            {"data": {"data": {"APP_KEY": "abc"}}},
            {"data": {"data": {"SHARED_KEY": "xyz"}}},
        ]
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        load_secrets()

        assert os.environ["APP_KEY"] == "abc"
        assert os.environ["SHARED_KEY"] == "xyz"
        assert mock_client.secrets.kv.v2.read_secret_version.call_count == 2

    @patch("config.vault_secrets.Client")
    def test_secret_prefix_stripped_from_path(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "valid-token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"KEY": "val"}}
        }
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        load_secrets()

        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="myapp", mount_point="secret"
        )

    @patch("config.vault_secrets.Client")
    def test_raises_on_vault_read_exception(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://localhost:8200")
        monkeypatch.setenv("VAULT_TOKEN", "valid-token")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "connection refused"
        )
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        with pytest.raises(
            ValueError, match="Exception while reading secrets from vault"
        ):
            load_secrets()

    @patch("config.vault_secrets.Client")
    def test_client_initialized_with_correct_params(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("VAULT_ADDR", "http://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.mytoken")
        monkeypatch.setenv("VAULT_SECRET_PATH", "secret/myapp")

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {}}
        }
        mock_client_cls.return_value = mock_client

        from config.vault_secrets import load_secrets

        load_secrets()

        mock_client_cls.assert_called_once_with(
            url="http://vault.example.com:8200", token="s.mytoken"
        )
