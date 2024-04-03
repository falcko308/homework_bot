import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exception

load_dotenv()

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
    tokens = (
        (PRACTICUM_TOKEN, 'TOKEN_PRACTICUM'),
        (TELEGRAM_TOKEN, 'TOKEN_TELEGRAM'),
        (TELEGRAM_CHAT_ID, 'CHAT_ID')
    )
    for token in tokens:
        if not token[0]:
            logging.critical(
                f'Отсутствует обязательная переменная: {token[1]}.'
            )
            sys.exit('Отсутствует одна из переменных окружения')
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение в Telegram не отправлено {error}')
        return False
    logging.debug(f'Сообщение в Telegram отправлено: {message}')
    return True


def get_api_answer(timestamp):
    """Проверка ответа сервиса."""
    param_dict = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logging.info('Отправлен запрос к API Практикума '
                 'URL: {url}, Заголовки: {headers}, '
                 'Время: {params} сек.'.format(**param_dict))
    try:
        response = requests.get(**param_dict)
    except Exception:
        text = ('Ссылка {url}, Заголовки: {headers}, '
                'Время: {params} недоступены')
        logging.error(text.format(**param_dict))
        raise ConnectionError(text.format(**param_dict))
    if response.status_code != HTTPStatus.OK:
        raise exception.InvalidResponseCode()
    return response.json()


def check_response(response):
    """проверяет ответ API на соответствие."""
    if not isinstance(response, dict):
        raise TypeError('Отсутствие словаря в ответе API')
    if 'homeworks' not in response:
        raise KeyError('Отсутствие ключа homeworks в ответе API')
    homework = response['homeworks']
    if not isinstance(homework, list):
        raise TypeError('Отсутствие списка домашних работ в ответе API')
    return homework


def parse_status(homework):
    """Получение информации о конкретной домашней работе статус этой работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except KeyError as error:
        logging.error(
            f'Ключ {error} отсутствует в информации о домашней работе'
        )
        raise KeyError(
            f'Ключ {error} отсутствует в информации о домашней работе'
        )
    if status not in HOMEWORK_VERDICTS:
        logging.error('Неизвестный статус домашней работы')
        raise Exception('Неизвестный статус домашней работы')
    else:
        verdict = HOMEWORK_VERDICTS[status]
        logging.info('Начали отправку сообщения в Telegram')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')

    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    current_report = ''
    prev_report = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                logging.debug('Задания отсутствуют!')
                continue
            message = parse_status(homework[0])
            if message != prev_report:
                send_message(bot, message)
                prev_report = message
        except exception.SendTelegramError as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        except Exception as error:
            message = f'Произошёл сбой в программе: {error}'
            logging.error(message)
            if message != current_report:
                send_message(bot, message)
                current_report = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(f'{__file__}.log', encoding='utf-8')],
        format=(
            '%(asctime)s - %(levelname)s - %(funcName)s - '
            '%(lineno)s - %(message)s'
        )
    )
    main()
