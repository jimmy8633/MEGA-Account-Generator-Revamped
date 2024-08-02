import argparse
import asyncio
import os
import sys
from typing import Tuple
from playwright.async_api import async_playwright

from services.alive import keepalive
from services.upload import upload_file
from services.extract import extract_credentials
from utilities.fs import (
    Config,
    concrete_read_config,
    read_config,
    write_config,
    write_default_config,
    save_credentials,
)
from utilities.web import (
    generate_mail,
    type_name,
    type_password,
    initial_setup,
    mail_login,
    get_mail,
)
from utilities.etc import (
    Credentials,
    p_print,
    clear_console,
    Colours,
    clear_tmp,
    reinstall_tenacity,
    check_for_updates,
    delete_default,
)

# Constants
DEFAULT_INSTALLS = [
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
    "C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
]

ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--window-position=0,0",
    "--ignore-certificate-errors",
    "--ignore-certificate-errors-spki-list",
    '--user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"',
]

# Ensure correct version of tenacity is installed
if sys.version_info.major == 3 and sys.version_info.minor <= 11:
    try:
        pass
    except AttributeError:
        reinstall_tenacity()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-ka", "--keepalive", action="store_true", help="Logs into the accounts to keep them alive.")
    parser.add_argument("-e", "--extract", action="store_true", help="Extracts the credentials to a file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Shows storage left while using keepalive function.")
    parser.add_argument("-f", "--file", help="Uploads a file to the account.")
    parser.add_argument("-p", "--public", action="store_true", help="Generates a public link to the uploaded file, use with -f")
    parser.add_argument("-l", "--loop", type=int, help="Loops the program for a specified amount of times.")
    return parser.parse_args()

def setup() -> Tuple[str, Config]:
    """Sets up the configs so everything runs smoothly."""
    config = read_config()
    if config is None:
        write_default_config()
        config = concrete_read_config()
    executable_path = config.executablePath or prompt_for_executable_path(config)
    return executable_path, config

def prompt_for_executable_path(config: Config) -> str:
    p_print("Failed to find a Chromium based browser. Please make sure you have one installed.", Colours.FAIL)
    executable_path = input("Please enter the path to a Chromium based browser's executable: ")
    if os.path.exists(executable_path):
        p_print("Found executable!", Colours.OKGREEN)
        write_config("executablePath", executable_path, config)
    else:
        p_print("Failed to find executable!", Colours.FAIL)
        sys.exit(1)
    return executable_path

def loop_registrations(loop_count: int, executable_path: str, config: Config):
    """Registers accounts in a loop."""
    for i in range(loop_count):
        p_print(f"Loop {i + 1}/{loop_count}", Colours.OKGREEN)
        clear_tmp()
        credentials = asyncio.run(generate_mail())
        asyncio.run(register(credentials, executable_path, config))

async def register(credentials: Credentials, executable_path: str, config: Config):
    """Registers and verifies a mega.nz account."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=ARGS, executable_path=executable_path)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await type_name(page, credentials)
        await type_password(page, credentials)
        mail = await mail_login(credentials)

        await asyncio.sleep(1.5)
        message = await get_mail(mail)

        await initial_setup(context, message, credentials)
        await asyncio.sleep(0.5)
        await browser.close()

        p_print("Verified account.", Colours.OKGREEN)
        p_print(f"Email: {credentials.email}\nPassword: {credentials.password}", Colours.OKCYAN)

        delete_default(credentials)
        save_credentials(credentials, config.accountFormat)

        if console_args.file:
            handle_file_upload(console_args.file, console_args.public, credentials)
    if not console_args.loop or console_args.loop <= 1:
        sys.exit(0)

def handle_file_upload(file_path: str, public: bool, credentials: Credentials):
    """Handles file upload logic."""
    file_size = os.path.getsize(file_path)
    if os.path.exists(file_path) and 0 < file_size < 2e10:
        if file_size >= 5e9:
            p_print("File is larger than 5GB, mega.nz limits traffic to 5GB per IP.", Colours.WARNING)
        upload_file(public, file_path, credentials)
    else:
        p_print("File not found.", Colours.FAIL)

if __name__ == "__main__":
    clear_console()
    check_for_updates()
    console_args = parse_args()

    executable_path, config = setup()
    if not executable_path:
        p_print("Failed while setting up!", Colours.FAIL)
        sys.exit(1)

    if console_args.extract:
        extract_credentials(config.accountFormat)
    elif console_args.keepalive:
        keepalive(console_args.verbose)
    elif console_args.loop and console_args.loop > 1:
        loop_registrations(console_args.loop, executable_path, config)
    else:
        clear_tmp()
        credentials = asyncio.run(generate_mail())
        asyncio.run(register(credentials, executable_path, config))
