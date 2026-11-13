import os
import sys
import re
import urllib.request
import http.cookiejar

FILE_ID = "1bxv6lBNhKIXBrN-47GN8ysxeisjyBT51"
OUTPUT_BUNDLE = "aasha_aios_v2_bootstrap_full.bundle"

def download_gdrive_file(file_id, output_path):
    print(f"Downloading {file_id} to {output_path}...")
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
    
    # 1. Initial request
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = opener.open(url)
    data = resp.read()
    
    # Check if we got the actual bundle or HTML confirmation page.
    # Size is not evidence: a Google sign-in page is ~1 MB and would pass a
    # length test, so only the bundle magic bytes may decide.
    if data.startswith(b'# v2 git bundle') or data.startswith(b'# v3 git bundle'):
        with open(output_path, "wb") as f:
            f.write(data)
        print(f"Downloaded directly: {len(data)} bytes")
        return True
    
    # Look for confirm token in HTML
    html = data.decode('utf-8', errors='ignore')
    match = re.search(r'confirm=([0-9A-Za-z_-]+)', html)
    confirm_token = match.group(1) if match else None
    
    if not confirm_token:
        # Check download_warning cookie
        for cookie in cj:
            if 'download_warning' in cookie.name:
                confirm_token = cookie.value
                break
                
    if not confirm_token:
        # Check href with confirm=
        match_href = re.search(r'href="([^"]+confirm=[^"&]+[^"]*)"', html)
        if match_href:
            download_url = "https://drive.google.com" + match_href.group(1).replace('&amp;', '&')
        else:
            download_url = None
    else:
        download_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
        
    if not download_url:
        print("Could not find confirmation token. HTML preview:")
        print(html[:1000])
        with open("gdrive_response.html", "w", encoding="utf-8") as f:
            f.write(html)
        return False
        
    print(f"Fetching with confirm URL: {download_url}")
    resp2 = opener.open(download_url)
    with open(output_path, "wb") as f:
        total = 0
        while True:
            chunk = resp2.read(1024 * 64)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (1024 * 1024) == 0:
                print(f"Read {total // (1024 * 1024)} MB...")
    print(f"Finished downloading {output_path}: {total} bytes")
    with open(output_path, "rb") as f:
        magic = f.read(14)
    if not (magic.startswith(b'# v2 git bundle') or magic.startswith(b'# v3 git bundle')):
        print(f"Rejected: {output_path} is not a git bundle (starts {magic[:40]!r}).")
        return False
    return True

if __name__ == "__main__":
    if not download_gdrive_file(FILE_ID, OUTPUT_BUNDLE):
        sys.exit(1)
