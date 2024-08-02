"""All functions related to the browser"""

import asyncio
import re
import string
import random
import sys
import pymailtm
import math
from faker import Faker
from playwright.async_api import async_playwright, Browser
from tenacity import retry, stop_after_attempt, wait_exponential

from pymailtm.pymailtm import CouldNotGetAccountException, CouldNotGetMessagesException

from utilities.etc import Credentials, p_print, Colours

fake = Faker()


def get_random_string(length):
	"""Generate a random string with a given length."""
	lower_letters = string.ascii_lowercase
	upper_letters = string.ascii_uppercase
	numbers = string.digits
	alphabet = lower_letters + upper_letters + numbers

	return "".join(random.choice(alphabet) for _ in range(length))


async def initial_setup(browser: Browser, message: str, credentials: Credentials):
    """Initial setup for the account."""
    confirm_link = re.findall(
        r'href="(https:\/\/mega\.nz\/#confirm[^ ][^"]*)', str(message)
    )[0]

    confirm_page = await browser.new_page()
    await confirm_page.goto(confirm_link)
    confirm_field = "#login-password2"
    await confirm_page.wait_for_selector(confirm_field)
    await confirm_page.click(confirm_field)
    await confirm_page.type(confirm_field, credentials.password)
    await confirm_page.click(".login-button")

    try:
        # Wait for the #freeStart element to be present and then scroll into view
        free_start_element = await confirm_page.wait_for_selector("#freeStart", timeout=60000)
        await free_start_element.scroll_into_view_if_needed()
        await confirm_page.wait_for_selector("#freeStart:visible", timeout=30000)
        await confirm_page.click("#freeStart")
    except TimeoutError:
        # Log page content for debugging
        content = await confirm_page.content()
        p_print("Timeout while waiting for #freeStart to be visible. Page content:\n" + content, Colours.FAIL)
        raise



async def mail_login(credentials: Credentials):
	"""Logs into the mail.tm account with the generated credentials"""
	while True:
		try:
			mail = pymailtm.Account(
				credentials.id, credentials.email, credentials.emailPassword
			)
			p_print("Retrieved mail successfully!", Colours.OKGREEN)
			return mail
		except CouldNotGetAccountException:
			continue


async def get_mail(mail):
    """Get the latest email from the mail.tm account with exponential backoff and max attempts."""
    base_delay = 1.5  # Base delay in seconds
    max_delay = 30  # Maximum delay in seconds
    max_attempts = 20  # Maximum number of retries
    attempt = 0

    while attempt < max_attempts:
        try:
            message = mail.get_messages()[0]
            p_print("Found mail!", Colours.OKGREEN)
            return message
        except (IndexError, CouldNotGetMessagesException):
            attempt += 1
            delay = min(base_delay * (2 ** attempt), max_delay)
            p_print(
                f"Failed to find mail... trying again in {delay} seconds.", Colours.WARNING
            )
            await asyncio.sleep(delay)

    p_print("Failed to find mail after maximum retries... exiting.", Colours.FAIL)
    raise CouldNotGetAccountException("Failed to find mail after maximum retries... exiting.")

#    sys.exit(1)



async def type_name(page, credentials: Credentials):
	"""Types name into the name fields."""
	name = str(fake.name()).split(" ", 2)
	firstname = name[0]
	lastname = name[1]
	await page.goto("https://mega.nz/register")
	await page.wait_for_selector("#register_form")
	await page.type("#register-firstname-registerpage2", firstname)
	await page.type("#register-lastname-registerpage2", lastname)
	await page.type("#register-email-registerpage2", credentials.email)


async def type_password(page, credentials: Credentials):
	"""Types passwords into the password fields."""
	await page.click("#register-password-registerpage2")
	await page.type("#register-password-registerpage2", credentials.password)
	await page.click("#register-password-registerpage3")
	await page.type("#register-password-registerpage3", credentials.password)
	await page.click("#register-check-registerpage2")

	# Evaluate JavaScript to click the checkbox element
	await page.evaluate("document.querySelector('.understand-check').click()")

	await page.click(".register-button")
	p_print("Registered account successfully!", Colours.OKGREEN)


async def generate_mail() -> Credentials:
    """Generate mail.tm account and return account credentials with exponential backoff and max attempts."""
    mail = pymailtm.MailTm()
    
    base_delay = 1  # Base delay in seconds
    max_delay = 30  # Maximum delay in seconds
    max_attempts = 30  # Maximum number of retries
    attempt = 0

    while attempt < max_attempts:
        try:
            account = mail.get_account()
            break
        except CouldNotGetAccountException:
            attempt += 1
            delay = min(base_delay * (2 ** attempt), max_delay)
            p_print(f"Retrying mail.tm account generation... (delay: {delay} seconds)", Colours.WARNING)
            await asyncio.sleep(delay)

    if attempt == max_attempts:
        p_print("Failed to generate mail.tm account after maximum retries", Colours.FAIL)
        raise CouldNotGetAccountException("Failed to generate mail.tm account after maximum retries")

    credentials = Credentials()
    credentials.email = account.address
    credentials.emailPassword = account.password
    credentials.password = get_random_string(14)
    credentials.id = account.id_
    return credentials