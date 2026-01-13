from pkahub.settings import BASE_DIR, MOLIMAGE_DIR
from pathlib import Path

datasetconfigs_folder=BASE_DIR / 'build/datasetconfigs'
sourcesconfigs_folder=BASE_DIR / 'build/sourcesconfigs'
molimage_dir=MOLIMAGE_DIR
buildlogs_folder=BASE_DIR / 'build/buildlogs'

exp_macro_pka_datapoints_folder=BASE_DIR / 'build/datafiles/data/exp_macro_pka_datapoints'
microstates_table_folder=BASE_DIR / 'build/datafiles/data/microspecies'
molecules_table_folder=BASE_DIR / 'build/datafiles/data/molecules'