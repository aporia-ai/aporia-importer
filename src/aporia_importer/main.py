import argparse
import logging
from pathlib import Path
from uuid import uuid4

import aporia
from aporia.pandas import pandas_to_dict

from .config import load_config
from .data_loader import load_data
from .logging_utils import DEFAULT_LOG_LEVEL, init_logging, LOG_LEVEL_OPTIONS


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line args.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="Path to yaml config file")
    parser.add_argument(
        "--log-level",
        required=False,
        choices=LOG_LEVEL_OPTIONS,
        default=DEFAULT_LOG_LEVEL,
        help="Logging level",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    init_logging(args.log_level)

    try:
        config = load_config(args.config)
        logging.info("Initializing Aporia SDK")
        aporia.init(
            token=config.token,
            host=config.aporia_host,
            port=config.aporia_port,
            environment=config.environment,
            verbose=True,
        )

        logging.info("Creating model version")
        model = aporia.create_model_version(
            model_id=config.model_id,
            model_version=config.model_version.name,
            model_type=config.model_version.type,
            features=config.model_version.features,
            predictions=config.model_version.predictions,
            raw_inputs=config.model_version.raw_inputs,
        )

        logging.info(f"Loading data from {config.source}, format: {config.format.value}")
        data = load_data(source=config.source, format=config.format)

        logging.info("Reporting predictions")
        for _, row in data.iterrows():
            # If you wish to modify your data before reporting it, do it here

            raw_inputs = None
            if config.model_version.raw_inputs is not None:
                raw_inputs = pandas_to_dict(row[config.model_version.raw_inputs.keys()])

            model.log_prediction(
                id=str(uuid4()),
                features=pandas_to_dict(row[config.model_version.features.keys()]),
                predictions=pandas_to_dict(row[config.model_version.predictions.keys()]),
                raw_inputs=raw_inputs,
            )

        model.flush()
        aporia.shutdown()
        logging.info("Finished")

    except Exception:
        logging.error("Importing data from cloud storage to Aporia failed.", exc_info=True)


if __name__ == "__main__":
    main()
