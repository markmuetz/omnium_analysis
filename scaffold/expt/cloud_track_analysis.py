import sys
import os
from logging import getLogger
import pickle

import numpy as np
from cloud_tracking import Tracker
from cloud_tracking.cloud_tracking_analysis import generate_stats, output_stats_to_file

from omnium import Analyser, ExptList
from omnium.utils import get_cube_from_attr

logger = getLogger('scaf.cta')


class CloudTrackAnalyser(Analyser):
    """Tracks clouds using method similar to Plant 2009.

    Change is due to temporal resolution of data being less, take account of this by first
    calculating spatial correlation then using this to project the cloud field at a given height
    forward in time. Most heavy lifting is handled by cloud_tracking package."""
    analysis_name = 'cloud_track_analysis'
    multi_file = True
    input_dir = 'omnium_output/{version_dir}/{expt}'
    input_filename_glob = '{input_dir}/atmos.???.cloud_analysis.nc'
    output_dir = 'omnium_output/{version_dir}/{expt}'
    output_filenames = ['{output_dir}/atmos.cloud_track_analysis.all_stats.pkl',
                        '{output_dir}/atmos.cloud_track_analysis.trackers.pkl',
                        ]
    uses_runid = True
    runid_pattern = 'atmos.(?P<runid>\d{3}).cloud_analysis.nc'
    min_runid = 480
    # No max.
    # max_runid = 308

    recursion_limit = 10000

    def load(self):
        self.load_cubes()

    def run(self):
        cubes = self.cubes

        self.trackers = {}
        self.all_stats = {}
        cloud_mask_id = 'cloud_mask'
        cloud_mask_cube = get_cube_from_attr(cubes, 'omnium_cube_id', cloud_mask_id)

        w_thresh_coord = cloud_mask_cube.coord('w_thres')
        qcl_thresh_coord = cloud_mask_cube.coord('qcl_thres')
        level_number_coord = cloud_mask_cube.coord('model_level_number')
        logger.debug(cloud_mask_cube.shape)

        w_cube = get_cube_from_attr(cubes, 'omnium_cube_id', 'w_slice')
        rho_cube = get_cube_from_attr(cubes, 'omnium_cube_id', 'rho_slice')

        expts = ExptList(self.suite)
        expts.find([self.task.expt])
        expt_obj = expts.get(self.task.expt)

        # height_level refers to orig cube.
        # height_level_index refers to w as it has already picked out the height levels.
        for height_level_index, level_number in enumerate(level_number_coord.points):
            for thresh_index in range(w_thresh_coord.shape[0]):
                # TODO: reinstate
                # if height_level_index != 1 and thresh_index != 1:

                # ONLY perform for both index == 1.
                if height_level_index != 1 or thresh_index != 1:
                    # Only perform for all height levels using thresh_index == 1,
                    # and all thresh_index for height_level_index == 1.
                    continue

                logger.debug('height_index, thresh_index: {}, {}'.format(height_level_index,
                                                                         thresh_index))

                w_thresh = w_thresh_coord.points[thresh_index]
                qcl_thresh = qcl_thresh_coord.points[thresh_index]
                labelled_clouds_cube_id = 'labelled_clouds_z{}_w{}_qcl{}'.format(level_number,
                                                                                 w_thresh,
                                                                                 qcl_thresh)
                labelled_clouds_cube = get_cube_from_attr(cubes,
                                                          'omnium_cube_id',
                                                          labelled_clouds_cube_id)

                cld_field = np.zeros(cloud_mask_cube[:, height_level_index, thresh_index, thresh_index].shape, dtype=int)
                cld_field_cube = cloud_mask_cube[:, height_level_index, thresh_index, thresh_index].copy()
                cld_field_cube.rename('cloud_field')

                for time_index in range(cloud_mask_cube.shape[0]):
                    labelled_clouds_ss = labelled_clouds_cube[time_index].data.astype(int)
                    cld_field[time_index] = labelled_clouds_ss
                cld_field_cube.data = cld_field

                tracker = Tracker(cld_field_cube.slices_over('time'), expt_obj.dx, expt_obj.dy,
                                  include_touching=True,
                                  touching_diagonal=True,
                                  ignore_smaller_equal_than=1,
                                  store_working=True)
                tracker.add_mass_flux_info(w_iter=w_cube[:, height_level_index].slices_over('time'),
                                           rho_iter=rho_cube[:, height_level_index].slices_over('time'))
                logger.debug('tracking clouds')
                tracker.track()
                logger.debug('grouping clouds')
                tracker.group()

                logger.debug('generating stats')
                stats = generate_stats(self.task.expt, tracker)
                self.trackers[(height_level_index, thresh_index)] = tracker
                self.all_stats[(height_level_index, thresh_index)] = stats

    def save(self, state, suite):
        old_recursion_limit = sys.getrecursionlimit()
        logger.debug('setting recursion limit to {}', self.recursion_limit)
        sys.setrecursionlimit(self.recursion_limit)
        with open(self.task.output_filenames[0], 'wb') as f:
            pickle.dump(self.all_stats, f)
        for tracker in self.trackers.values():
            # Cannot be pickled.
            tracker.cld_field_iter = None
            if tracker.can_calc_mass_flux:
                tracker.w_iter = None
                tracker.rho_iter = None
        with open(self.task.output_filenames[1], 'wb') as f:
            pickle.dump(self.trackers, f)
        logger.debug('setting recursion limit back to {}', old_recursion_limit)

    def display_results(self):
        self.append_log('displaying results')
        figpath = self.file_path('cloud_tracking')

        for tracker_key in self.trackers.keys():
            height_level_index, thresh_index = tracker_key
            stats = self.all_stats[tracker_key]
            tracker = self.trackers[tracker_key]
            filename = 'atmos.cloud_tracking_z{}_t{}.'.format(height_level_index, thresh_index)

            output_stats_to_file(self.task.expt, os.path.dirname(figpath), filename + 'txt',
                                 tracker, stats)
