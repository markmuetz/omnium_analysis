import os
import shutil
from configparser import ConfigParser

import omnium
import scaffold


def setup_module():
    suite_dir = os.getenv('SCAFFOLD_SUITE_UAN388_DIR', None)
    assert suite_dir, 'Env set SCAFFOLD_SUITE_UAN388_DIR to your u-an388 test suite'
    assert os.path.exists(suite_dir)
    if os.path.exists(os.path.join(suite_dir, 'omnium_output')):
        shutil.rmtree(os.path.join(suite_dir, 'omnium_output'))
    rose_app_conf_fn = os.path.join(os.path.dirname(os.path.dirname(scaffold.__file__)),
                                    'rose-app.conf')
    shutil.copy(rose_app_conf_fn, os.path.join(suite_dir, 'app/omnium', 'rose-app.conf' ))


def test_00_check_all_analysers_in_use():
    suite_dir = os.getenv('SCAFFOLD_SUITE_UAN388_DIR')
    os.chdir(suite_dir)
    cp = ConfigParser()
    cp.read('app/omnium/rose-app.conf')
    analysis_names = []
    for run_type in ['cycle', 'expt', 'suite']:
        runcontrol_sec = 'runcontrol_{}'.format(run_type)
        runcontrol = cp[runcontrol_sec]
        for ordered_analysis, enabled_str in sorted(runcontrol.items()):
            assert enabled_str == 'True'
            analysis_name = ordered_analysis[3:]
            analysis_names.append(analysis_name)
    scaffold_analysis_names = [a.analysis_name for a in scaffold.analyser_classes]
    assert set(analysis_names) == set(scaffold_analysis_names)


def test_01_run_cycle_analysis():
    suite_dir = os.getenv('SCAFFOLD_SUITE_UAN388_DIR')
    os.chdir(suite_dir)
    omnium.omnium_main(['omnium', '-D', '-b', 'run', '-s', 'test',
                        '-t', 'cycle', '--all', 'S0', 'S4'])

def test_02_run_expt_analysis():
    suite_dir = os.getenv('SCAFFOLD_SUITE_UAN388_DIR')
    os.chdir(suite_dir)
    omnium.omnium_main(['omnium', '-D', '-b', 'run', '-s', 'test',
                        '-t', 'expt', '--all', 'S0', 'S4'])

def test_03_run_suite_analysis():
    suite_dir = os.getenv('SCAFFOLD_SUITE_UAN388_DIR')
    os.chdir(suite_dir)
    omnium.omnium_main(['omnium', '-D', '-b', 'run', '-s', 'test',
                        '-t', 'suite', '--all', 'S0', 'S4'])
