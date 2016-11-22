# tests: lint, mypy

import sys
import os

from neuralmonkey.logging import log
from neuralmonkey.config.configuration import Configuration
from neuralmonkey.checking import check_dataset_and_coders
from neuralmonkey.learning_utils import initialize_tf, run_on_dataset, \
    print_dataset_evaluation
from neuralmonkey.runners.ensemble_runner import EnsembleRunner

CONFIG = Configuration()
CONFIG.add_argument('output', str)
CONFIG.add_argument('encoders', list, cond=lambda l: len(l) > 0)
CONFIG.add_argument('decoder')
CONFIG.add_argument('postprocess')
CONFIG.add_argument('evaluation', cond=list)
CONFIG.add_argument('runner')
CONFIG.add_argument('threads', int, required=False, default=4)

# ignore arguments which are just for training
CONFIG.ignore_argument('val_dataset')
CONFIG.ignore_argument('trainer')
CONFIG.ignore_argument('name')
CONFIG.ignore_argument('train_dataset')
CONFIG.ignore_argument('random_seed')
CONFIG.ignore_argument('epochs')
CONFIG.ignore_argument('batch_size')
CONFIG.ignore_argument('tests_datasets')
CONFIG.ignore_argument('initial_variables')
CONFIG.ignore_argument('validation_period')
CONFIG.ignore_argument('logging_period')
CONFIG.ignore_argument('minimize')
CONFIG.ignore_argument('save_n_best')
CONFIG.ignore_argument('overwrite_output_dir')


def default_variable_file(args):
    variables_file = os.path.join(args.output, "variables.data.best")
    cont_index = 1

    def continuation_file():
        return os.path.join(args.output,
                            "variables.data.cont-{}.best".format(cont_index))
    while os.path.exists(continuation_file()):
        variables_file = continuation_file()
        cont_index += 1

    return variables_file


def initialize_for_running(ini_file, variable_files):
    """Prepares everything that is necessary for running a model.

    Arguments:
        ini_file: Path to the configuration file.

    Returns:
        A tuple of parsed configuration (inlucding built computation graph)
        and a TensorFlow session with already loaded model variables.
    """
    # pylint: disable=no-member
    args = CONFIG.load_file(ini_file)
    print("")

    if variable_files is None:
        default_varfile = default_variable_file(args)

        log("Default variable file '{}' will be used for loading variables."
            .format(default_varfile))

        variable_files = [default_varfile]

    if len(variable_files) == 1 and not isinstance(args.runner, EnsembleRunner):
        log("Warning: useless more variable files without ensemble runner",
            color="red")

    sessions = []

    for vfile in variable_files:
        if not os.path.exists(vfile):
            log("Variable file {} does not exist".format(vfile),
                color="red")
            exit(1)

        sess, _ = initialize_tf(vfile, args.threads)
        sessions.append(sess)

    print("")
    return args, sessions

def main():
    # pylint: disable=no-member,broad-except
    if len(sys.argv) != 3:
        print("Usage: run.py <run_ini_file> <test_datasets>")
        exit(1)

    test_datasets = Configuration()
    test_datasets.add_argument('test_datasets')
    test_datasets.add_argument('variables')

    datasets_args = test_datasets.load_file(sys.argv[2])
    args, sessions = initialize_for_running(
        sys.argv[1], datasets_args.variables)

    print("")

    try:
        for dataset in datasets_args.test_datasets:
            check_dataset_and_coders(dataset, args.encoders)
    except Exception as exc:
        log(str(exc), color='red')
        exit(1)

    for dataset in datasets_args.test_datasets:
        _, _, evaluation = run_on_dataset(
            sessions, args.runner, args.encoders + [args.decoder], args.decoder,
            dataset, args.evaluation, args.postprocess, write_out=True)
        if evaluation:
            print_dataset_evaluation(dataset.name, evaluation)
