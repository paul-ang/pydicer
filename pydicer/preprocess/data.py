import logging

import pandas as pd

import pydicom
import numpy as np

from pydicer.constants import (
    PET_IMAGE_STORAGE_UID,
    RT_DOSE_STORAGE_UID,
    RT_PLAN_STORAGE_UID,
    RT_STRUCTURE_STORAGE_UID,
    CT_IMAGE_STORAGE_UID,
)
from pydicer.quarantine.treat import copy_file_to_quarantine

logger = logging.getLogger(__name__)


class PreprocessData:
    """
    Class for preprocessing the data information into a dicionary that holds the data in a
    structured hierarchy

    Args:
        working_directory (Path): The working directory in which the data is stored (Output of the
        Input module)
    """

    def __init__(self, working_directory, output_directory):
        self.working_directory = working_directory
        self.output_directory = output_directory

    # TODO: need to find the linked series UID
    def preprocess(self):
        """
        Function to preprocess information regarding the data located in an Input working directory

        Returns: res_dict (pd.DataFrame): containing a row for each DICOM file that was
           preprocessed, with the following columns:
            - patient_id: PatientID field from the DICOM header
            - study_uid: StudyInstanceUID field from the DICOM header
            - series_uid: SeriesInstanceUID field from the DICOM header
            - modality: Modailty field from the DICOM header
            - sop_class_uid: SOPClassUID field from the DICOM header
            - sop_instance_uid: SOPInstanceUID field from the DICOM header
            - for_uid: FrameOfReferenceUID field from the DICOM header
            - file_path: The path to the file (as a pathlib.Path object)
            - slice_location: The real-world location of the slice (used for imaging modalities)
            - referenced_uid: The SeriesUID referenced by this DICOM file for RTSTRUCT
              and RTDOSE, the SOPInstanceUID of the structure set referenced by an RTPLAN.
            - referenced_for_uid: The ReferencedFrameOfReferenceUID referenced by this DICOM file

        """
        df = pd.DataFrame(
            columns=[
                "patient_id",
                "study_uid",
                "series_uid",
                "modality",
                "sop_class_uid",
                "sop_instance_uid",
                "for_uid",
                "file_path",
                "slice_location",
                "referenced_uid",
                "referenced_for_uid",
            ]
        )
        files = self.working_directory.glob("**/*.dcm")

        for file in files:
            ds = pydicom.read_file(file, force=True)

            try:

                dicom_type_uid = ds.SOPClassUID

                res_dict = {
                    "patient_id": ds.PatientID,
                    "study_uid": ds.StudyInstanceUID,
                    "series_uid": ds.SeriesInstanceUID,
                    "modality": ds.Modality,
                    "sop_class_uid": dicom_type_uid,
                    "sop_instance_uid": ds.SOPInstanceUID,
                    "file_path": str(file),
                }

                if "FrameOfReferenceUID" in ds:
                    res_dict["for_uid"] = ds.FrameOfReferenceUID

                if dicom_type_uid == RT_STRUCTURE_STORAGE_UID:

                    try:
                        referenced_series_uid = (
                            ds.ReferencedFrameOfReferenceSequence[0]
                            .RTReferencedStudySequence[0]
                            .RTReferencedSeriesSequence[0]
                            .SeriesInstanceUID
                        )
                        res_dict["referenced_uid"] = referenced_series_uid
                    except AttributeError:
                        logger.warning("Unable to determine Reference Series UID")

                    try:
                        # Check other tags for a linked DICOM
                        # e.g. ds.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID
                        # Potentially, we should check each referenced
                        referenced_frame_of_reference_uid = ds.ReferencedFrameOfReferenceSequence[
                            0
                        ].FrameOfReferenceUID
                        res_dict["referenced_for_uid"] = referenced_frame_of_reference_uid
                    except AttributeError:
                        logger.warning("Unable to determine Referenced Frame of Reference UID")

                elif dicom_type_uid == RT_PLAN_STORAGE_UID:

                    try:
                        referenced_sop_instance_uid = ds.ReferencedStructureSetSequence[
                            0
                        ].ReferencedSOPInstanceUID
                        res_dict["referenced_uid"] = referenced_sop_instance_uid
                    except AttributeError:
                        logger.warning("Unable to determine Reference Series UID")

                elif dicom_type_uid == RT_DOSE_STORAGE_UID:

                    try:
                        referenced_sop_instance_uid = ds.ReferencedRTPlanSequence[
                            0
                        ].ReferencedSOPInstanceUID
                        res_dict["referenced_uid"] = referenced_sop_instance_uid
                    except AttributeError:
                        logger.warning("Unable to determine Reference Series UID")

                elif dicom_type_uid in (CT_IMAGE_STORAGE_UID, PET_IMAGE_STORAGE_UID):

                    image_position = np.array(ds.ImagePositionPatient, dtype=float)
                    image_orientation = np.array(ds.ImageOrientationPatient, dtype=float)

                    image_plane_normal = np.cross(image_orientation[:3], image_orientation[3:])

                    slice_location = (image_position * image_plane_normal)[2]

                    res_dict["slice_location"] = slice_location

                else:
                    raise ValueError(
                        f"Could not determine DICOM type {ds.Modality} {dicom_type_uid}."
                    )

                # Add as a row to the DataFrame
                df = df.append(res_dict, ignore_index=True)

            except Exception as e:  # pylint: disable=broad-except
                # Broad except ok here, since we will put these file into a
                # quarantine location for further inspection.
                logger.error(
                    "Error parsing file %s: %s. Placing file into Quarantine folder...", file, e
                )
                copy_file_to_quarantine(file, self.output_directory, e)

        # Sort the the DataFrame by the patient then series uid and the slice location, ensuring
        # that the slices are ordered correctly
        df = df.sort_values(["patient_id", "series_uid", "slice_location"])

        return df
