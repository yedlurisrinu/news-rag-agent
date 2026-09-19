import json
import logging
import pytest
from unittest.mock import patch, mock_open, MagicMock


class TestSetupLogging:

    def test_loads_config_from_json_file(self, tmp_path):
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {},
            "root": {"level": "INFO", "handlers": []}
        }
        config_file = tmp_path / "logging_config.json"
        config_file.write_text(json.dumps(config))

        with patch("config.logging_setup.Path") as mock_path, \
             patch("logging.config.dictConfig") as mock_dict_config:
            mock_path.return_value.parent.parent = tmp_path
            from config.logging_setup import setup_logging
            setup_logging()
            mock_dict_config.assert_called_once_with(config)

    def test_falls_back_to_basic_config_when_file_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError("not found")), \
             patch("logging.basicConfig") as mock_basic:
            from config.logging_setup import setup_logging
            setup_logging()
            mock_basic.assert_called_once_with(level=logging.INFO)

    def test_falls_back_to_basic_config_when_json_is_invalid(self):
        with patch("builtins.open", mock_open(read_data="not valid json")), \
             patch("logging.basicConfig") as mock_basic:
            from config.logging_setup import setup_logging
            setup_logging()
            mock_basic.assert_called_once_with(level=logging.INFO)

    def test_falls_back_to_basic_config_when_dict_config_raises(self):
        config = {"version": 1}
        with patch("builtins.open", mock_open(read_data=json.dumps(config))), \
             patch("logging.config.dictConfig", side_effect=ValueError("bad config")), \
             patch("logging.basicConfig") as mock_basic:
            from config.logging_setup import setup_logging
            setup_logging()
            mock_basic.assert_called_once_with(level=logging.INFO)

    def test_accepts_custom_config_file_name(self):
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {},
            "root": {"level": "DEBUG", "handlers": []}
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(config))) as mock_file, \
             patch("logging.config.dictConfig"):
            from config.logging_setup import setup_logging
            setup_logging(config_file="custom_logging.json")
            opened_path = mock_file.call_args[0][0]
            assert "custom_logging.json" in opened_path

    def test_dict_config_called_with_parsed_json(self):
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"simple": {"format": "%(message)s"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "simple"
                }
            },
            "root": {"level": "WARNING", "handlers": ["console"]}
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(config))), \
             patch("logging.config.dictConfig") as mock_dict_config:
            from config.logging_setup import setup_logging
            setup_logging()
            mock_dict_config.assert_called_once_with(config)