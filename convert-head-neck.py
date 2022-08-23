import time
from pathlib import Path
from pydicer.input.test import TestInput
from pydicer import PyDicer
import multiprocessing

def run_pipeline(src_path):
    # Configure working directory
    directory = Path(src_path)

    # Fetch some test DICOM data to convert
    dicom_directory = directory.joinpath("dicom")

    # Create the PyDicer tool object and add the dicom directory as an input location
    pydicer = PyDicer(directory)
    pydicer.add_input(dicom_directory)

    # Run the pipeline
    pydicer.run_pipeline()

def test(folder_name):
    print('Sleeping for 0.5 seconds')
    time.sleep(0.5)
    print('Finished sleeping')
    print(folder_name)

if __name__ == '__main__':
    folder1 = "/Volumes/Samsung_T5/Datasets/Parallel-converted-head-neck/CHUM"
    folder2 = "/Volumes/Samsung_T5/Datasets/Parallel-converted-head-neck/CHUS"
    folder3 = "/Volumes/Samsung_T5/Datasets/Parallel-converted-head-neck/HGJ"
    folder4 = "/Volumes/Samsung_T5/Datasets/Parallel-converted-head-neck/HMR"

    folders = [folder1, folder2, folder3, folder4]
    start = time.perf_counter()
    processes = []
    for folder in folders:
        p = multiprocessing.Process(target=run_pipeline, args=(folder,))
        p.start()
        processes.append(p)

    # Joins all the processes
    for p in processes:
        p.join()

    finish = time.perf_counter()
    print(f'Finished in {round(finish - start, 2)} secounds')

    print("Finished converting!")