import random
from time import sleep

import requests
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bot import send_message
import logging
import json

# setup logging
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

known_days = {}
known_sessions = {}


def get_sessions(cookies, storage):
    auth_jwt = cookies[0]['value']
    logging.info(f"session id: {auth_jwt}")
    if auth_jwt is None:
        raise Exception("no session id")

    storage = storage['vuex']
    session_jwt = json.loads(storage)['user']['authToken']

    url = "https://booking.bbdc.sg/bbdc-back-service/api/booking/c2practical/listPracSlotReleased"

    payload = "{\n    \"courseType\": \"2B\",\n    \"insInstructorId\": \"\",\n    \"stageSubDesc\": \"Subject 1.1\",\n    \"subVehicleType\": \"Circuit\",\n    \"stageSubNo\": \"1.01\"\n}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15\'',
        'JSESSIONID': session_jwt,
        'Authorization': auth_jwt,
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    return


def app(config):
    logging.info("parse config")

    username = config["bbdc"]["username"]
    password = config["bbdc"]["password"]

    # bot
    bot_token = config["telegram"]["token"]
    chat_id = config["telegram"]["chat_id"]
    enable_bot = config["telegram"]["enabled"]

    # chrome host
    chrome_host = config["chromedriver"]["host"]

    # implicit_wait = 5
    # browser.implicitly_wait(implicit_wait)

    # connect to chrome
    logging.info("connect to selenium")
    browser = webdriver.Remote(
        '{:}/wd/hub'.format(chrome_host), DesiredCapabilities.CHROME)
    browser.get('https://booking.bbdc.sg/#/login?redirect=%2Fbooking%2Findex')

    try:
        # login BBDC
        logging.info("login")
        idLogin = browser.find_element_by_id('input-8')
        idLogin.send_keys(username)
        idLogin = browser.find_element_by_id('input-15')
        idLogin.send_keys(password)
        loginButton = browser.find_element_by_class_name('v-btn')
        loginButton.click()

        # proceed unsure form (Chrome)
        browser.switch_to.default_content()

        # click practical button
        sleep(20)
        logging.info("click practical button")
        practical = browser.find_element_by_xpath(
            '//*[@id="app"]/div/div/main/div/div/div[2]/div/div[1]/div/div/div[1]/div/div[2]/div/div[2]')
        practical.click()

        sleep(5)
        logging.info("click booking button")
        book_next = browser.find_element_by_xpath(
            '/html/body/div[1]/div/div/main/div/div/div[2]/div/div[1]/div/div/div[2]/div/div[2]/div[1]/div[1]/div/button')
        book_next.click()

        # if have booked lesson, click continue
        try:
            continue_button = browser.find_element_by_xpath('/html/body/div[1]/div[3]/div/div/div[2]/button[2]')
            continue_button.click()
        except NoSuchElementException:
            logging.info("No continue button")

        # GET COOKIE AND USE API
        # sessions = get_sessions(browser.get_cookies(), browser.execute_script("return window.localStorage;"))

        # parse calendar
        while True:
            logging.info("parsing calendar...")
            parse_calendar(bot_token, browser, chat_id, enable_bot)
            logging.info("wait for 30-120 seconds before refresh...")
            # sleep(random.randint(30, 120))
            logging.info("refreshing...")
            browser.refresh()

    except Exception as e:
        logging.exception(e)
        raise
    finally:
        browser.quit()


def parse_calendar(bot_token, browser, chat_id, enable_bot):
    sleep(random.randint(10, 20))
    calendar = browser.find_element_by_xpath(
        '/html/body/div[1]/div/div/main/div/div/div[2]/div/div[2]/div[1]/div[1]/div[1]/div[4]/div/div/div')
    days_to_notify = []
    new_known_days = {}
    for day in calendar.find_elements_by_class_name('v-btn__content'):
        logging.info(f"Day found: {day.text}")
        new_known_days[day.text] = True
        if day.text not in known_days:
            days_to_notify.append(day.text)
            logging.warning(f"[NEW] New day found: {day.text}")
        day.click()
        sleep(random.randint(1, 3))

    known_days.clear()
    known_days.update(new_known_days)

    # send message to telegram
    logging.info(f"New days found: {days_to_notify}")
    if len(days_to_notify) > 0 and enable_bot:
        send_message(bot_token, chat_id, f"New days found: {days_to_notify}")
    # parse slots
    sessions = browser.find_elements_by_class_name('sessionList')
    new_known_sessions = {}

    for s in sessions:
        if s.text == '':  # skip empty blocks
            continue

        date, total, name, time, cost = s.text.splitlines()
        logging.info(f"Session found: {date} {time}")
        if f'{date} {time}' not in known_sessions:
            known_sessions[f'{date} {time}'] = True
            logging.warning(f"[NEW] New session found: {date} {time}")
            if enable_bot:
                send_message(bot_token, chat_id, f"New session found: {date} {time}")
        new_known_sessions[f'{date} {time}'] = True

    known_sessions.clear()
    known_sessions.update(new_known_sessions)
