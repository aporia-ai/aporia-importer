import argparse
import logging
from pathlib import Path
from uuid import uuid4
from dask.distributed import Client
from dask_kubernetes import KubeCluster

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
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    init_logging(args.log_level)

    try
        # Horizontally scale on K8s if necessary.
        if args.enable_k8s:
            # FUTURE: Worker spec path should be an argument to the script.
            cluster = KubeCluster('/aporia-importer/config/worker-spec.yaml')
            cluster.adapt(minimum=args.k8s_workers_min, maximum=args.k8s_workers_max)

            # Connect Dask to the cluster
            client = Client(cluster)

        # co\("Finished")

    except Exception:
        logging.error("Importing data from cloud storage to Aporia failed.", exc_info=True)


if __name__ == "__main__":
    main()
