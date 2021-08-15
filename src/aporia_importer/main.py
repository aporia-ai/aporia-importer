import argparse
import logging
from pathlib import Path
from uuid import uuid4
from dask.distributed import Client
from dask_kubernetes import KubeCluster
from dask_cloudprovider.aws import EC2Cluster

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
    parser.add_argument(
        "--enable-k8s",
        action='store_true',
        help="Whether aporia-importer should run k8s workers to horizontally scale the workload",
    )
    parser.add_argument(
        "--k8s-workers-min",
        type=int,
        default=1,
        help="Minimum K8s workers (--enable-k8s is required for this)",
    )
    parser.add_argument(
        "--k8s-workers-max",
        type=int,
        default=3,
        help="Maximum K8s workers (--enable-k8s is required for this)",
    )
    parser.add_argument(
        "--k8s-worker-spec-path",
        type=str,
        help="Path to the Dask worker spec (see https://kubernetes.dask.org/en/latest/kubecluster.html)",
    )
    return parser.parse_args()


def process_partition(df, config):

    print("inside process_partition")

    # Might need to reinitialize Aporia because this can happen in a different process on a remote machine
    aporia.init(
        token=config.token,
        host=config.aporia_host,
        port=config.aporia_port,
        environment=config.environment,
        verbose=True,
    )

    model = aporia.Model(
        model_id=config.model_id,
        model_version=config.model_version.name,
    )

    # Iterate rows and log to Aporia
    for _, row in df.iterrows():
        # NOTE TO USER: 
        # If you wish to modify your data before logging it, do it here

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


def log_data(config):
    # Initialize Aporia & create version
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

    # Load data
    logging.info(f"Loading data from {config.source}, format: {config.format.value}")
    df = load_data(source=config.source, format=config.format)

    # Log data
    logging.info("Logging predictions")
    df.map_partitions(process_partition, config=config).compute()


def main():
    """Main entry point."""
    args = parse_args()
    init_logging(args.log_level)

    # Load user config
    config = load_config(args.config)

    # Horizontally scale on K8s if necessary.
    if args.enable_k8s:
        with KubeCluster(args.k8s_worker_spec_path) as cluster:
            cluster.adapt(minimum=args.k8s_workers_min, maximum=args.k8s_workers_max)

            # Connect Dask to the cluster
            with Client(cluster) as client:
                log_data(config)
    else:
        log_data(config)

if __name__ == "__main__":
    main()
