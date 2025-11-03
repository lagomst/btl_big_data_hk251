#request.py
import sys
import requests
import asyncio
import httpx

from io import BytesIO
from fastapi import UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from tempfile import SpooledTemporaryFile

GDRIVE_DIRECT_URL = "https://docs.google.com/uc?export=download&confirm=1"

async def download_google_drive_file(file_id: str, filename: str = "downloaded_file") -> UploadFile:
    async with httpx.AsyncClient() as client:
        response = await client.get(GDRIVE_DIRECT_URL, params={"id": file_id, "confirm": 1}, follow_redirects=True)
        response.raise_for_status()

        content = response.content

        print("DEBUG: Response's header: ", response.headers)
    
        spooled = SpooledTemporaryFile()
        spooled.write(content)
        spooled.seek(0)

        return StarletteUploadFile(filename=filename, file=spooled, headers=response.headers)

async def download_onedrive_file(shared_url: str) -> StarletteUploadFile:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(shared_url)
        resp.raise_for_status()
        content = resp.content
        # content_type = resp.headers.get("content-type", "application/octet-stream")
        
        # Try extract filename from headers
        cd = resp.headers.get("content-disposition", "")
        filename = "downloaded_onedrive_file"
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip("\"; ")

        # Wrap in UploadFile-like for insert_file()
        spooled = SpooledTemporaryFile()
        spooled.write(content)
        spooled.seek(0)
        return StarletteUploadFile(filename=filename, file=spooled, headers=resp.headers)

async def get_file_from_url(url: str):
    if url.startswith('https://drive.google.com'):
        lower_part = url.split("/file/d/")[1]
        file_id = (lower_part.split("/")[0]).strip()
        return download_google_drive_file(file_id)

def download_file_from_google_drive(file_id, destination):
    URL = "https://docs.google.com/uc?export=download&confirm=1"

    session = requests.Session()

    response = session.get(URL, params={"id": file_id, "confirm": 1}, stream=True)
    # token = get_confirm_token(response)

    # if token:
    #     params = {"id": file_id, "confirm": token}
    #     response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value

    return None


def save_response_content(response, destination):
    CHUNK_SIZE = 32768

    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)


    

def main():
    if len(sys.argv) >= 3:
        file_id = sys.argv[1]
        destination = sys.argv[2]
    else:
        file_id = "TAKE_ID_FROM_SHAREABLE_LINK"
        destination = "DESTINATION_FILE_ON_YOUR_DISK"
    print(f"dowload {file_id} to {destination}")
    download_file_from_google_drive(file_id, destination)

def one_drive():
    if len(sys.argv) >= 2:
        file_url = sys.argv[1]
    else:
        file_url = "TAKE_URL_FROM_SHAREABLE_LINK"

    print(f"download {file_url}")
    file = asyncio.run(download_onedrive_file(file_url))
    from pprint import pprint
    pprint(dict(file.headers))

if __name__ == "__main__":
    one_drive()