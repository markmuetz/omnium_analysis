import os
from logging import getLogger

import numpy as np

import iris

from omnium.analyser import Analyser
from omnium.utils import get_cube_from_attr
from cloud_tracking.utils import label_clds
from cloud_tracking import Tracker
from cloud_tracking.cloud_tracking_analysis import output_stats

logger = getLogger('om.cta')


class CloudTrackAnalyser(Analyser):
    analysis_name = 'cloud_track_analysis'
    multi_file = True

    def load(self):
        self.append_log('Override load')

        cloud_mask_cubes = []
        cloud_mask_id = 'cloud_mask'
        for filename in self.filenames:
            cubes = iris.load(filename)
            cloud_mask_cube = get_cube_from_attr(cubes, 'omnium_cube_id', cloud_mask_id)
            cloud_mask_cubes.append(cloud_mask_cube)

        self.cubes = iris.cube.CubeList(cloud_mask_cubes).concatenate()
        self.append_log('Override loaded')

    def run_analysis(self):
        cubes = self.cubes

        cloud_mask_id = 'cloud_mask'
        cloud_mask_cube = get_cube_from_attr(cubes, 'omnium_cube_id', cloud_mask_id)

        w_thresh_coord = cloud_mask_cube.coord('w_thres')
        level_number_coord = cloud_mask_cube.coord('model_level_number')
        logger.debug(cloud_mask_cube.shape)

        # height_level refers to orig cube.
        # height_level_index refers to w as it has already picked out the height levels.
        for height_level_index, height_level in enumerate(level_number_coord.points):
            for thresh_index in range(w_thresh_coord.shape[0]):
                cld_field = np.zeros(cloud_mask_cube[:, height_level_index, thresh_index, thresh_index].shape, dtype=int)
                cld_field_cube = cloud_mask_cube[:, height_level_index, thresh_index, thresh_index].copy()
                cld_field_cube.rename('cloud_field')

                for time_index in range(cloud_mask_cube.shape[0]):
                    cloud_mask_ss = cloud_mask_cube[time_index,
                                                    height_level_index,
                                                    thresh_index,
                                                    thresh_index].data.astype(bool)
                    max_label, cld_labels = label_clds(cloud_mask_ss, True)
                    cld_field[time_index] = cld_labels
                cld_field_cube.data = cld_field

                tracker = Tracker(cld_field_cube.slices_over('time'), show_working=True)
                tracker.track()
                # proj_cld_field_cube = cld_field_cube.copy()
                # proj_cld_field_cube.data = tracker.proj_cld_field.astype(float)
                # iris.save(proj_cld_field_cube, 'output/{}_proj_cld_field.nc'.format(expt))

                tracker.group()
                # TODO: Hacky.
                # Force creation of output_dir (hacky).
                dummy_path = self.figpath('tracks')
                output_dir = os.path.dirname(dummy_path)
                prefix = '{}_z{}_t{}_'.format(os.path.basename(dummy_path), height_level_index, thresh_index)
                stats_for_expt = output_stats({self.expt: tracker}, output_dir, prefix=prefix)
                stats = stats_for_expt[self.expt]
