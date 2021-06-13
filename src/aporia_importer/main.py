import argparse
from pathlib import Path
from uuid import uuid4

import aporia
from aporia.pandas import pandas_to_dict
import dask.dataframe as dd

from .config import load_config


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line args.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="Path to yaml config file")

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    config = load_config(args.config)

    aporia.init(
        token=config.token,
        host=config.aporia_host,
        port=config.aporia_port,
        environment=config.environment,
        verbose=True,
    )

    model = aporia.create_model_version(
        model_id=config.model_id,
        model_version=config.model_version.name,
        model_type=config.model_version.type,
        features=config.model_version.features,
        predictions=config.model_version.predictions,
        raw_inputs=config.model_version.raw_inputs,
    )

    data = dd.read_csv(config.source)

    for _, row in data.iterrows():
        model.log_prediction(
            id=str(uuid4()),
            features=pandas_to_dict(row[config.model_version.features.keys()]),
            predictions=pandas_to_dict(row[config.model_version.predictions.keys()]),
        )

    model.flush()
    aporia.shutdown()


if __name__ == "__main__":
    main()
