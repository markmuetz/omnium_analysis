from omnium.converter import FF2NC_Converter


class CycleConverter(FF2NC_Converter):
    analysis_name = 'cycle_converter'
    single_file = True
    input_dir = 'share/data/history/{expt}'
    input_filename_glob = '{input_dir}/atmos.???.pp?'
    output_dir = 'share/data/history/{expt}'
    output_filenames = ['{output_dir}/atmos.{runid:03}.{stream}.nc']

    uses_runid = True
    runid_pattern = 'atmos.(?P<runid>\d{3}).(?P<stream>pp\d)'

    force = True
    delete = False
