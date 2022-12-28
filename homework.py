import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException

from exceptions import TokenError, InvalidResponseCodeError, TelegramSendError

logging.basicConfig(filename='__file__' + '.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    ('%(asctime)s - %(levelname)s '
     '- %(message)s - %(filename)s '
     '- %(funcName)s - %(lineno)d строка')
)
handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKEN_NOT_FOUND = 'Токен {} не найден!'
RESPONSE_ERROR = ("Ошибка соединения, статус: {status} "
                  "Причина: {reason}, {text} "
                  "endpoint: {url}, headers: {headers} "
                  "params: {params}")
CONNECT_ERROR = ("Ошибка {error} подключения к {url}."
                 " UNIX время в запросе: {params}.")
CHANGED_STATUS = ('Изменился статус проверки работы "{homework_name}".'
                  ' {verdicts}')
TOKEN_ERROR = 'Ошибка в токенах.'
ERROR_MESSAGE = 'Сбой в работе программы: {}'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {message}. {error}'
ERROR_NOT_DICT = 'Ответ вернул не словарь, а {type}'
ERROR_NOT_LIST = 'Ошибка: домашка - не список, а {type}'
ERROR_STATUS = 'Неизвестный статус работы: {status}'


def check_tokens():
    """Проверяем, что есть все токены."""
    flag = True
    for name in TOKENS:
        if globals()[name] is None:
            logging.critical(TOKEN_NOT_FOUND.format(name))
            flag = False
    return flag


def send_message(bot, message):
    """Отправляет сообщение в telegram."""
    try:
        logger.debug('Отправка сообщения в Телеграм.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        message_error = SEND_MESSAGE_ERROR.format(
            message=message, error=error)
        logger.error(message_error, exc_info=True)
        raise TelegramSendError(message_error)


def get_api_answer(timestamp):
    """Отправляем запрос к API и получаем список домашних работ."""
    parameters = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**parameters)
    except RequestException as error:
        raise ConnectionError(
            CONNECT_ERROR.format(**parameters, error=error)
        )
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeError(
            RESPONSE_ERROR.format(
                status=response.status_code,
                reason=response.reason,
                text=response.text,
                **parameters
            )
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            ERROR_NOT_DICT.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            ERROR_NOT_LIST.format(type=type(response)))
    return homeworks


def parse_status(homework):
    """Извлечение статуса работы домашнего задания."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(ERROR_STATUS.format(status))
    return CHANGED_STATUS.format(
        homework_name=homework.get("homework_name"),
        verdicts=HOMEWORK_VERDICTS[status])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise TokenError(TOKEN_ERROR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = ERROR_MESSAGE.format(error)
            logger.error(message)
            try:
                bot.send_message(TELEGRAM_CHAT_ID, message)
            except Exception as error:
                logger.exception(SEND_MESSAGE_ERROR.format(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

    # from unittest import TestCase, mock, main as uni_main
    # ReqEx = requests.RequestException
    # JSON = {'error': 'testing'}
    # JSON = {'homeworks': [{'homework_name': 'test', 'status': 'test'}]}
    # JSON = {'homeworks': 1}

    # class TestReq(TestCase):
    #     @mock.patch('requests.get')
    #     def test_raised(self, rq_get):
    #         rq_get.side_effect = mock.Mock(
    #             side_effect=ReqEx('testing'))
    #         main()
    #
    #
    # class TestReq(TestCase):
    #     @mock.patch('requests.get')
    #     def test_error(self, rq_get):
    #         resp = mock.Mock()  # Главный трюк
    #         resp.json = mock.Mock(
    #             eturn_value = JSON)
    #         rq_get.return_value = resp  # такой JSON
    #         main()  # Все подготовили, запускаем
    #
    # uni_main()
