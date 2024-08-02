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
    return config

async def register(credentials: Credentials, config: Config, chosen_browser=None):
    """Registers and verifies a mega.nz account."""

    # Check if browsers are installed
    async with async_playwright() as p:
        available_browsers = await p.chromium.browsers(), await p.firefox.browsers(), await p.webkit.browsers()
        if not any(available_browsers):
            print("No browsers found! Installing Playwright browsers...")
            await install_playwright_browsers()

    # Choose browser if not provided
    if not chosen_browser:
        browser_options = ["Chromium", "Firefox", "WebKit"]
        chosen_browser = browser_options[int(input("Choose a browser (1 - Chromium, 2 - Firefox, 3 - WebKit): ")) - 1]

    async with async_playwright() as p:
        browser_func = getattr(p, chosen_browser.lower()).launch
        browser = await browser_func(headless=True, args=ARGS)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        await type_name(page, credentials)
        await type_password(page, credentials)
