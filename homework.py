import exceptions
import logging
import os
import requests
import sys
import telegram
import time

from http import HTTPStatus
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
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
    """Проверяем, что есть все токены."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в telegram."""
    try:
        logger.debug('Отправка сообщения в Телеграм.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        message_error = f'Ошибка отправки сообщения {error}'
        logger.error(message_error)
        raise exceptions.TelegramSendError(message_error)


def get_api_answer(timestamp):
    """Отправляем запрос к API и получаем список домашних работ."""
    response_dict = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logger.info(
        "Запрос к {url}. "
        "UNIX время: {params[from_date]}.".format(**response_dict)
    )
    try:
        response = requests.get(**response_dict)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.InvalidResponseCodeError(
                "Ошибка соединения, статус: {status}"
                " Причина: {reason}, {text}".format(
                    status=response.status_code,
                    reason=response.reason,
                    text=response.text
                )
            )
        return response.json()
    except Exception as error:
        raise ConnectionError(
            "Ошибка {error} подключения к {url}. "
            "UNIX время в запросе: "
            "{params[from_date]}.".format(**response_dict, error=error)
        )


def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Начало проверки ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ вернул не словарь')
    if 'homeworks' not in response or 'current_date' not in response:
        raise TypeError('Ответ от API пустой.')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        raise TypeError('Ошибка: домашка - не список')
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        message = 'Отсутствует ключ "homework_name" в ответе API'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Отсутствует ключ "status" в ответе API'
        logger.error(message)
        raise KeyError(message)
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус работы: {homework_status}'
        logger.error(message)
        raise Exception(message)
    return (f'Изменился статус проверки работы "{homework.get("homework_name")}":'
            f' {HOMEWORK_VERDICTS[homework_status]}')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_cache_message = ''
    if not check_tokens():
        logger.critical('Oшибка переменных окружения')
        sys.exit('Oшибка переменных окружения')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            hw_list = check_response(response)
            if hw_list:
                send_message(bot, parse_status(hw_list[0]))
            else:
                message = 'Нет новых статусов'
                logger.debug(message)
                raise Exception(message)
        except Exception as error:
            logger.error(error)
            message_error = str(error)
            if message_error != error_cache_message:
                send_message(bot, message_error)
                error_cache_message = message_error
        finally:
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
