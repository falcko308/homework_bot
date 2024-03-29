import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)


PRACTICUM_TOKEN = os.getenv('TOKEN_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN_TELEGRAM')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение в Telegram отправлено: {message}')
    except Exception as error:
        logging.error(f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(timestamp):
    """Проверка ответа сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error(f'Сбой в работе программы:'
                          f'Эндпоинт {ENDPOINT} недоступен.'
                          f'Код ответа API:{response.status_code}')
            raise response.raise_for_status()

    except Exception as error:
        logging.error(f'Эндпойнт недоступен: {error}')
        raise Exception(f'Эндпойнт недоступен: {error}')
    return response.json()


def check_response(response):
    """проверяет ответ API на соответствие."""
    if not isinstance(response, dict):
        logging.error('Отсутствие словаря в ответе API')
        raise TypeError('Отсутствие словаря в ответе API')
    if 'homeworks' not in response:
        logging.error('Отсутствие ключа homeworks в ответе API')
        raise KeyError('Отсутствие ключа homeworks в ответе API')
    if not isinstance(response['homeworks'], list):
        logging.error('Отсутствие списка домашних работ в ответе API')
        raise TypeError('Отсутствие списка домашних работ в ответе API')
    return response['homeworks']


def parse_status(homework):
    """Получение информации о конкретной домашней работе статус этой работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except Exception as error:
        logging.error(
            f'Ключ {error} отсутствует в информации о домашней работе'
        )
        raise Exception(
            f'Ключ {error} отсутствует в информации о домашней работе'
        )

    try:
        verdict = HOMEWORK_VERDICTS[status]
        logging.info('Сообщение подготовлено для отправки')
    except Exception as error:
        logging.error(f'Неизвестный статус домашней работы: {error}')
        raise Exception(f'Неизвестный статус домашней работы: {error}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют переменные окружения')
        sys.exit('Отсутствует одна из переменных окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework[0])
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
