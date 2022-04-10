
import cv2
import datetime
import imagehash
import logging as LOG
import os
import PIL.Image
import subprocess
import sys

from typing import List

# TODO: Check for location metadata and query Google location API?

LOG_NAME = "log.txt"
ERROR_CODE_SUCCESS = 0
ERROR_CODE_FAIL = 1
ERROR_CODE_PARAMETERS = 2
ERROR_CODE_DEPENDENCIES = 3

HEIC = '.heic'
JPG = '.jpg'
JPEG = '.jpeg'
MOV = '.mov'
MP4 = '.mp4'
PNG = '.png'
SUPPORTED_IMAGE_EXTENSIONS = [JPG, JPEG, HEIC, PNG]
SUPPORTED_VIDEO_EXTENSIONS = [MOV, MP4]
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS + SUPPORTED_VIDEO_EXTENSIONS

EXIFTOOL = "\\exiftool.exe"
EXIFTOOL_PATH = os.getcwd() + EXIFTOOL

POWERSHELL = "powershell.exe"
POWERSHELL_POLICY_BYPASS_CURRENT_USER = \
    "Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope CurrentUser"
HEIC2JPG = "\\ConvertTo-Jpeg.ps1"

EXIF_DATETIME_ORIGINAL = "Date/Time Original"   # Date Taken
EXIF_DATETIME_DIGITIZED = "Create Date"         # Date Created
EXIF_DATETIME = "Modify Date"                   # Date Modified
EXIF_MEDIA_CREATED = "Media Create Date"        # Media Created

INDEX_COUNT = 0
INDEX_NAME = 1
INDEX_PATH = 0
INDEX_EXTENSION = 1
file_data_hash = {}
target_directory = ""


class MediaObject:

    def __init__(self, file_path, extension):
        self.file_path = file_path
        self.extension = extension
        self.exif = {}
        self.date_value = ""
        self.image = None
        self.capture = None
        self.copy = False

        self.new_name = ""
        self.new_file = ""
        self.heic_jpg_path = None

        if (extension in SUPPORTED_IMAGE_EXTENSIONS):
            self.open = self.openImage
            self.close = self.closeImage
        elif (extension in SUPPORTED_VIDEO_EXTENSIONS):
            self.open = self.openVideo
            self.close = self.closeVideo
        else:
            LOG.warning(f"Unsupported file extension - {extension}")
            raise Exception

    def __repr__(self) -> str:
        return f"File: {self.file_path}{self.extension}\n" \
               f"Date Value: {self.date_value}"

    def __str__(self) -> str:
        return f"{self.file_path}{self.extension}"

    def heicToJpg(self):
        ''' https://github.com/DavidAnson/ConvertTo-Jpeg '''

        # Start subprocess for ConvertTo-Jpeg.ps1
        powershell_command = f"{os.getcwd() + HEIC2JPG} '{self.file_path}'"
        LOG.debug(f"PowerShell Command: {powershell_command}")
        completed = subprocess.run([POWERSHELL, powershell_command],
                                   check=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        LOG.debug(f"ConvertTo-Jpeg.ps1 return code: {completed.returncode}")
        if (completed.returncode != ERROR_CODE_SUCCESS):
            LOG.warning("HEIC To JPEG Image Conversion Failed")
        else:
            self.file_path += JPG

        return

    def open(self):
        LOG.warning("MediaObject::open Undefined")

    def close(self):
        LOG.warning("MediaObject::close Undefined")

    def openImage(self):
        self.image = PIL.Image.open(self.file_path)

    def closeImage(self):
        self.image.close()

    def openVideo(self):
        # Open first image with OpenCV and convert to Pillow image
        self.capture = cv2.VideoCapture(self.file_path)
        status, frame = self.capture.read()
        cv2_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.image = PIL.Image.fromarray(cv2_image)

    def closeVideo(self):
        self.capture.release()

    def process(self):
        LOG.debug(f"process::file_path: {self.file_path}")
        LOG.debug(f"process::extension: {self.extension}")

        # Use exiftool.exe to get the EXIF data of the media file
        LOG.debug(f"EXIFTOOL PATH: {EXIFTOOL_PATH}")
        process_result = subprocess.Popen([EXIFTOOL_PATH, self.file_path],
                                          universal_newlines=True,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT)

        for line in process_result.stdout:
            x = line.replace("\n", "").split(":", 1)
            self.exif[x[0].strip()] = x[1].strip()

        # Get the media file date time
        date_exif = ""
        if EXIF_DATETIME_ORIGINAL in self.exif:
            date_exif = self.exif[EXIF_DATETIME_ORIGINAL]
        elif EXIF_MEDIA_CREATED in self.exif:
            date_exif = self.exif[EXIF_MEDIA_CREATED]
        elif EXIF_DATETIME_DIGITIZED in self.exif:
            date_exif = self.exif[EXIF_DATETIME_DIGITIZED]
        elif EXIF_DATETIME in self.exif:
            date_exif = self.exif[EXIF_DATETIME]
        else:
            LOG.exception("process::Missing a date entry")
            path = self.file_path
            if (os.path.getmtime(path) < os.path.getctime(path)):
                date = os.path.getmtime(path)
            else:
                date = os.path.getctime(path)
            date = str(datetime.datetime.fromtimestamp(date))
            date_exif = date.replace("-", "")
            # raise KeyError

        # Filter datetime for year and month
        LOG.debug(f"process::date_exif: {date_exif}")
        date_exif = date_exif.replace(".", "_")
        date_exif = date_exif.replace(" ", "_")
        self.date_value = date_exif.replace(":", "")
        year = self.date_value[:4]
        month = self.date_value[4:6]
        self.new_name = self.date_value[:15]    # Truncate milliseconds
        LOG.debug(f"process::year: {year}")
        LOG.debug(f"process::month: {month}")
        LOG.debug(f"process::new_name: {self.new_name}")

        # Generate a JPG copy if HEIC image
        if (self.extension == HEIC):
            self.heicToJpg()

        # Open the media file
        self.open()

        # Hash the media file and log result in copy dictionary
        hashed_image = str(imagehash.average_hash(self.image))
        LOG.debug(f"process::hashed_image: {hashed_image}")
        if hashed_image not in file_data_hash:
            file_data_hash[hashed_image] = [0, self.new_name]
        else:
            self.copy = True
            file_data_hash[hashed_image][INDEX_COUNT] += 1

        # Close media handle
        self.close()

        # Build new file name
        self.new_file = self.new_name
        if (self.copy is not False):
            # Apply copy tag
            self.new_file += \
                f"_copy{file_data_hash[hashed_image][INDEX_COUNT]}"
        self.new_file += self.extension
        LOG.debug(f"process::new_file: {self.new_file}")

        # Remove JPG copy of HEIC file
        if (self.extension == HEIC):
            self.heic_jpg_path = self.file_path
            self.file_path = os.path.splitext(self.file_path)[INDEX_PATH]
            if (self.heic_jpg_path is not None):
                LOG.debug(f"process::Remove File: {self.heic_jpg_path}")
                os.remove(self.heic_jpg_path)
            else:
                LOG.warning("process::Invalid JPG path to remove.")

        # Create year directory
        year_path = os.path.join(target_directory, year)
        os.makedirs(year_path, exist_ok=True)

        # Create month directory
        month_path = os.path.join(year_path, month)
        os.makedirs(month_path, exist_ok=True)
        self.new_file_path = os.path.join(month_path, self.new_file)

        # Rename file
        try:
            LOG.debug(f"process::file_path: {self.file_path}")
            LOG.debug(f"process::new_file_path: {self.new_file_path}")
            os.rename(self.file_path, self.new_file_path)

        except (FileExistsError):
            # Add hash if name already exists.
            hashed_image = hex(int(hashed_image, 16))
            self.new_name += \
                f"_copy{file_data_hash[hashed_image][INDEX_COUNT]}" + \
                f"_{hashed_image[2:6]}" + \
                self.extension

            self.new_file_path = os.path.join(month_path, self.new_name)
            os.rename(self.file_path, self.new_file_path)

        return


def directoryEnumerate(directory) -> List[str]:
    ''' Enumerates the files in each directory recursively and adds them to
        a list. '''

    # Add all elements of the iterable list (os.walk(<path>), to
    # files_list (.extend()).
    files_list = []
    path_dirs = []
    for (dir_path, path_dirs, dir_files) in os.walk(directory):
        files_list.extend(dir_files)
        LOG.debug(f"directoryEnumerate::directory: {directory}")
        LOG.debug(f"directoryEnumerate::path_dirs: {path_dirs}")
        LOG.debug(f"directoryEnumerate::files_list: {files_list}")
        break

    path_list = [os.path.join(directory, f) for f in files_list]
    for dir in path_dirs:
        res = directoryEnumerate(os.path.join(directory, dir))
        path_list += res

    LOG.debug(f"directoryEnumerate::path_list: {path_list}")
    return path_list


if __name__ == "__main__":
    ''' https://exiftool.org/TagNames/EXIF.html '''

    # Configure Logging
    LOG.basicConfig(
        filename=LOG_NAME,
        filemode='a',
        format='%(asctime)s.%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
        level=LOG.DEBUG)

    # Get script working directory
    current_path = os.getcwd()

    # Check for exiftool.exe and ConvertTo-Jpeg.ps1 dependencies
    if (os.path.exists(current_path + EXIFTOOL) is not True):
        LOG.error(f"Missing {EXIFTOOL}")
        sys.exit(ERROR_CODE_DEPENDENCIES)

    if (os.path.exists(current_path + HEIC2JPG) is not True):
        LOG.error(f"Missing {HEIC2JPG}")
        sys.exit(ERROR_CODE_DEPENDENCIES)

    # Configure PowerShell for HEIC conversion
    powershell_command = POWERSHELL_POLICY_BYPASS_CURRENT_USER
    completed = subprocess.run([POWERSHELL, powershell_command],
                               check=True,
                               stdout=subprocess.PIPE)

    # Get target directories from input parameters, and make results directory
    try:
        input_directory = os.path.normpath(sys.argv[1])
        input_directory = os.path.join(current_path, input_directory)
        target_directory = os.path.join(current_path, "results")
        os.makedirs(target_directory, exist_ok=True)
        LOG.debug(f"main::input_directory: {input_directory}")
        LOG.debug(f"main::target_directory: {target_directory}")

    except (IndexError):
        LOG.exception("Input parameters incorrect; Missing input directory")
        sys.exit(ERROR_CODE_PARAMETERS)

    # Enumerate each file in the directory
    files_list = directoryEnumerate(input_directory)

    # Process each file
    for file_path in files_list:
        extension = os.path.splitext(file_path)[INDEX_EXTENSION].lower()
        try:
            media_file = MediaObject(file_path, extension)
            media_file.process()
        except (Exception) as e:
            LOG.exception(e)
            continue

    # Write to a text file a list of copie from the hash map
    hash_text = open(os.path.join(target_directory, "hash.txt"), 'a')
    for key in file_data_hash:
        value = file_data_hash[key][INDEX_COUNT]
        name = file_data_hash[key][INDEX_NAME]
        hash_text.write(f"{name} : {key} : {value} \n")

    hash_text.close()
    LOG.info("Done")
    input("Press any key to exit...")
    sys.exit(ERROR_CODE_SUCCESS)
