import argparse
import logging
import yaml
from pathlib import Path
from dask.config import expand_environment_variables
from dask.distributed import Client, get_worker
from dask_kubernetes import KubeCluster
from dask_kubernetes.common.objects import make_pod_from_dict
import aporia

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
    parser.add_argument(
        "--k8s-scheduler-spec-path",
        type=str,
        help="Path to the Dask scheduler spec (see https://kubernetes.dask.org/en/latest/kubecluster.html)",
    )
    return parser.parse_args()


def process_partition(df, config):
    import aporia
    import uuid

    # Are we running in a Dask worker?
    worker = None
    try:
        worker = get_worker()
    except ValueError:
        # Dask is throwing an Exception if there are no workers (local execution).
        pass

    # Initialize Aporia in this worker if necessary
    if worker is not None and not worker.data.get("IsAporiaInitialized", False):
        aporia.init(
            token=config.token,
            host=config.aporia_host,
            port=config.aporia_port,
            environment=config.environment,
            verbose=True,
        )

        worker.data["IsAporiaInitialized"] = True


    # Load Aporia model
    model = aporia.Model(config.model_id, config.model_version.name)

    # Iterate rows and log to Aporia
    for _, row in df.iterrows():
        # NOTE: If you wish to modify your data before logging it, do it here

        raw_inputs = None
        if config.model_version.raw_inputs is not None:
            raw_inputs = aporia.pandas.pandas_to_dict(row[config.model_version.raw_inputs.keys()])
        
        model.log_prediction(
            id=str(uuid.uuid4()),
            features=aporia.pandas.pandas_to_dict(row[config.model_version.features.keys()]),
            predictions=aporia.pandas.pandas_to_dict(row[config.model_version.predictions.keys()]),
            raw_inputs=raw_inputs,
        )

    model.flush()



def log_data(config):
    # Initialize Aporia
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

    # Load data
    logging.info(f"Loading data from {config.source}, format: {config.format.value}")
    df = load_data(source=config.source, format=config.format)

    # Log data
    logging.info("Logging predictions")
    df.map_partitions(process_partition, config=config, meta=(None, 'f8')).compute()


def main():
    """Main entry point."""
    args = parse_args()
    init_logging(args.log_level)

    # Load user config
    config = load_config(args.config)

    # Horizontally scale on K8s if necessary.
    if args.enable_k8s:
        # Load scheduler pod template from path (for some reason this isn't necessary for the worker template)
        with open(args.k8s_scheduler_spec_path) as k8s_scheduler_spec:
            scheduler_pod_template = make_pod_from_dict(expand_environment_variables(yaml.safe_load(k8s_scheduler_spec)))

        with KubeCluster(pod_template=args.k8s_worker_spec_path, scheduler_pod_template=scheduler_pod_template) as cluster:
            cluster.adapt(minimum=args.k8s_workers_min, maximum=args.k8s_workers_max)

            # Connect Dask to the cluster
            with Client(cluster) as client:
                log_data(config)
    else:
        log_data(config)

        

if __name__ == "__main__":
    main()
