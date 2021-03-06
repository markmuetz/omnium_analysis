import os
from logging import getLogger
import pickle
import gc

import numpy as np
import matplotlib.pyplot as plt
import scipy.interpolate as interpolate

from scaffold.expt_settings import EXPT_DETAILS

from omnium import Analyser
from omnium.utils import cm_to_inch

logger = getLogger('scaf.ctlp')


def plot_mf_lifecycle(ax, tracker, group_type='all'):
    """Calculate mass_flux_lifecycle and plot results into ax, for the given tracker

    group_type can be 'all', 'simile' or 'complex'
    """
    # Only do for groups with at least 2 clouds in them.
    groups = [g for g in tracker.groups if len(g) >= 2]

    # Recalculate all cloud fractions using the 'simple' formulation.
    # This is where cloud fractions for split clouds are simply proportional
    # to the area of the split clouds. As opposed to the method in Plant 2009,
    # which can cause difficulties (-ve numbers, infinities) with a longer timestep.
    for cg in groups:
        cg.frac_method = 'simple'
        cg._calc_cld_fractions()

    lifecycle_mass_flux = []
    lengths = []
    # Boolean array that says whether simple or complex (linear or not).
    is_simple = []

    # For each group, get the mass_flux_lifecycle(s).
    # There will be one mass_flux_lifecycle for every end cloud in the group.
    for cg in groups:
        for mass_flux_lifecycle in cg.get_cld_lifetime_properties('mass_flux'):
            f_mass_flux = interpolate.interp1d(np.linspace(0, 1, len(mass_flux_lifecycle)),
                                               mass_flux_lifecycle)
            lifecycle_mass_flux.append(f_mass_flux(np.linspace(0, 1, 100)))

            # Only do once.
            lengths.append(len(mass_flux_lifecycle))
            is_simple.append(cg.is_linear)

    lifecycle_mass_flux = np.array(lifecycle_mass_flux)
    lengths = np.array(lengths)
    is_simple = np.array(is_simple, dtype=int)

    # 5 min per lenght unit, 6 -> 30 min...
    lifetimes = [
        (lengths <= 6, 'b', 't <= 30 min'),
        ((lengths > 6) & (lengths <= 12), 'g', '30 min < t <= 60 min'),
        (lengths > 12, 'r', '60 min < t'),
    ]

    for lifetime_filt, colour, label in lifetimes:
        if group_type == 'simple':
            group_filt = is_simple == 1
        elif group_type == 'complex':
            group_filt = is_simple == 0
        elif group_type == 'all':
            group_filt = np.ones_like(is_simple, dtype=bool)

        filt = lifetime_filt & group_filt
        mf25, mf_median, mf75 = np.percentile(lifecycle_mass_flux[filt], [25, 50, 75], axis=0)

        ax.plot(np.linspace(0, 1, 100), mf_median / 1e7, linestyle='-', color=colour, label=label)
        ax.plot(np.linspace(0, 1, 100), mf25 / 1e7, linestyle='--', color=colour)
        ax.plot(np.linspace(0, 1, 100), mf75 / 1e7, linestyle='--', color=colour)


class CloudTrackLifecyclesPlot(Analyser):
    """Plot lifecycle figures based on analysing all cloud groups in a given tracker.

    Uses the 'simple' method for calculating cloud fractions - not to be confused with 'simple'
    clouds, i.e. clouds that have no merges or splits (sorry for the naming!)."""
    analysis_name = 'cloud_track_lifecycle_plot'
    multi_expt = True
    input_dir = 'omnium_output/{version_dir}/{expt}'
    input_filename = '{input_dir}/atmos.cloud_track_analysis.trackers.pkl'
    output_dir = 'omnium_output/{version_dir}/suite_{expts}'
    output_filenames = ['{output_dir}/atmos.cloud_track_lifecycle_plot.dummy']

    def load(self):
        # Trackers take up a lot of memory. Load on demand then delete them.
        self.tracker_fns = dict(zip(self.task.expts, self.task.filenames))

    def _load_trackers(self, expt):
        fn = self.tracker_fns[expt]
        self.append_log('loading {} for {}'.format(fn, expt))
        with open(fn, 'rb') as f:
            return pickle.load(f)

    def run(self):
        pass

    def save(self, state, suite):
        with open(self.task.output_filenames[0], 'w') as f:
            f.write('done')

    def display_results(self):
        if not len(self.task.expts) == 4:
            logger.debug('can only run with 4 expts')
            return

        height_level_index, thresh_index = (1, 1)
        fig, axes = plt.subplots(2, 2, figsize=cm_to_inch(16, 14))

        for i, (expt, ax) in enumerate(zip(self.task.expts, axes.flatten())):
            trackers = self._load_trackers(expt)

            tracker = trackers[(1, 1)]

            if expt in EXPT_DETAILS:
                expt_name = EXPT_DETAILS[expt][0]
            else:
                expt_name = expt

            plot_mf_lifecycle(ax, tracker)

            if i in [0, 2]:
                ax.set_ylabel('mass flux ($\\times 10^{7}$ kg s$^{-1}$)')
            else:
                plt.setp(ax.get_yticklabels(), visible=False)

            if i in [2, 3]:
                ax.set_xlabel('fraction of lifetime')
            else:
                plt.setp(ax.get_xticklabels(), visible=False)

            ax.set_xlim((0, 1))
            ax.set_ylim((0, 7))

            ax.set_title('{}'.format(expt_name))
            if i == 1:
                ax.legend(loc='upper right')

            del trackers
            del tracker
            gc.collect()

        plt.tight_layout()
        plt.savefig(self.file_path('mf_lifecycle_z{}_t{}'.format(height_level_index,
                                                                 thresh_index)))
