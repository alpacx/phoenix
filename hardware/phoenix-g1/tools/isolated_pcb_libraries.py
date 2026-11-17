"""Copy the local footprint environment into isolated PCB experiments."""
import shutil
def copy_libraries(source_study, target_study):
    shutil.copy2(source_study/'pcb/fp-lib-table',target_study/'pcb/fp-lib-table')
    source=source_study.parent/'emmc-system/system/kicad'
    target=target_study.parent/'emmc-system/system/kicad'
    target.mkdir(parents=True,exist_ok=True)
    for folder in source.glob('*.pretty'):
        shutil.copytree(folder,target/folder.name,dirs_exist_ok=True)
