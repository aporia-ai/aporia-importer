from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from yaml import safe_load

from aporia_importer.logging_utils import DEFAULT_LOG_LEVEL
from .data_loader import DataFormat


@dataclass
class ModelVersion:
    """Model version details and schema."""

    name: str
    type: str
    predictions: dict[str, str]
    features: dict[str, str]
    raw_inputs: Optional[dict[str, str]] = None


@dataclass
class Config:
    """Importer configuration."""

    source: str
    format: DataFormat
    environment: str
    token: str
    model_id: str
    model_version: ModelVersion
    log_level: str
    aporia_host: Optional[str] = None
    aporia_port: Optional[int] = None


def load_config(config_path: Path) -> Config:
    """Load config from yaml config file.

    Args:
        config_path: Path to config file

    Returns:
        Config object.
    """
    with open(config_path, "r") as config_file:
        config_dict = safe_load(config_file)

    return Config(
        source=config_dict["source"],
        format=DataFormat(config_dict["format"]),
        environment=config_dict["environment"],
        token=config_dict["token"],
        model_id=config_dict["model_id"],
        model_version=ModelVersion(
            name=config_dict["model_version"]["name"],
            type=config_dict["model_version"]["type"],
            predictions=config_dict["model_version"]["predictions"],
            features=config_dict["model_version"]["features"],
            raw_inputs=config_dict["model_version"].get("raw_inputs"),
        ),
        log_level=config_dict.get("log_level", DEFAULT_LOG_LEVEL),
        aporia_host=config_dict.get("aporia_host"),
        aporia_port=config_dict.get("aporia_port"),
    )
