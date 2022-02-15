from distutils.core import setup
import py2exe
import requests
from tqdm import tqdm
import os

DOWNLOAD_URL_EXIF_VERSION = "Image-ExifTool-12.40.tar.gz"
DOWNLOAD_URL_EXIF = "https://exiftool.org/" + DOWNLOAD_URL_EXIF_VERSION
DOWNLOAD_URL_CONVERT = "https://raw.githubusercontent.com/DavidAnson/ConvertTo-Jpeg/main/ConvertTo-Jpeg.ps1"

# setup(
#     options={'py2exe': {'bundle_files': 1, 'compressed': True}},
#     console=[{"script": "organize.py"}],
#     zipfile=None
# )

# response = requests.get(DOWNLOAD_URL_EXIF, stream=True)
# with open(DOWNLOAD_URL_EXIF_VERSION, "wb") as handle:
#     for data in tqdm(response.iter_content()):
#         handle.write(data)

# importing the "tarfile" module
import tarfile

# open file
file = tarfile.open(os.getcwd() + "\\" + DOWNLOAD_URL_EXIF_VERSION)

# extracting file
file.extractall(f"./{DOWNLOAD_URL_EXIF_VERSION}")

file.close()
