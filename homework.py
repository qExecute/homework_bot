import logging
import os
import sys
import time
import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

from exceptions import HomeworkStatusesException, SendMessageException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

ERROR_ENDPOINT_MESSAGE = (
    f'Эндпоинт {ENDPOINT} недоступен. '
    f'Код ответа API: {{status_code}}'
)
MISSING_TOKENS_WARNING = 'Пропущены следующие токены: {missing_tokens}'
MISSING_ENV_VARS_ERROR = (
    'Отсутствуют обязательные переменные окружения'
)
PROGRAM_FAILURE_MESSAGE = 'Сбой в работе программы: {error}, {error_class}'
STATUS_CHANGE_MESSAGE = (
    'Изменился статус проверки работы "{homework_name}". {verdict}'
)
STATUS_MISMATCH_ERROR = 'Статус домашней работы не соответствует ожидаемому'
LOG_INFO_MESSAGE_SEND_MESSAGE = 'Бот начал отправку сообщения в Telegramm'
LOG_DEBUG_MESSAGE_SEND_MESSAGE = 'Отправлено сообщение: {message}'
SEND_MESSAGE_FAILURE_MESSAGE = 'Сбой при отправке сообщения в Telegram'
LOG_DEBUG_MESSAGE_GET_API_ANSWER = 'Запущена функция get_api_answer().'
ERROR_ENDPOINT_MESSAGE = 'Эндпоинт {ENDPOINT} недоступен. ' \
                         'Код ответа API: {status_code}'
REQUEST_FAILURE_MESSAGE = 'Сбой при запросе к эндпоинту'
LOG_DEBUG_MESSAGE_CHECK_RESPONSE = 'Запущена функция check_response().'
API_RESPONSE_TYPE_ERROR = 'Ошибка типа данных в ответе API. Ожидается словарь.'
MISSING_KEY_ERROR = 'Отсутствует ключ "{key}" в ответе API.'
HOMEWORKS_TYPE_ERROR = 'Под ключем "homeworks" ожидается список.'
MISSING_KEY_ERROR_DICT = 'В словаре нет запрашиваемого ключа'
LOG_DEBUG_MESSAGE_PARSE_STATUS = 'Выполнена функция parse_status().'
API_REQUEST_ERROR = 'Ошибка при запросе к API-эндпоинту.'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения в Telegram.'
PROGRAM_FAILURE_MESSAGE = 'Произошла ошибка выполнения программы: ' \
                          '{error_class}: {error}'
NO_UPDATES_MESSAGE = 'Обновлений нет.'


def send_message(bot, message) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.info(LOG_INFO_MESSAGE_SEND_MESSAGE)
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except ConnectionError as e:
        raise ConnectionError(SEND_MESSAGE_FAILURE_MESSAGE) from e
    else:
        log_debug_message = LOG_DEBUG_MESSAGE_SEND_MESSAGE.format(
            message=message
        )
        logging.debug(log_debug_message)


def get_api_answer(current_timestamp):
    """Возвращает ответ API приведенный к типу данных python."""
    logging.debug(LOG_DEBUG_MESSAGE_GET_API_ANSWER)
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        homework_statuses.raise_for_status()  # Проверка статуса ответа
    except requests.exceptions.RequestException as e:
        raise ConnectionError(REQUEST_FAILURE_MESSAGE) from e
    if homework_statuses.status_code == HTTPStatus.OK:
        return homework_statuses.json()
    else:
        message = ERROR_ENDPOINT_MESSAGE.format(
            ENDPOINT=ENDPOINT,
            status_code=homework_statuses.status_code
        )
        raise ConnectionError(message)


def check_response(response) -> list:
    """Проверяет ответ API на cоответствие."""
    logging.debug(LOG_DEBUG_MESSAGE_CHECK_RESPONSE)
    if not isinstance(response, dict):
        raise TypeError(API_RESPONSE_TYPE_ERROR)
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        raise KeyError(MISSING_KEY_ERROR.format(key=error))
    if isinstance(homeworks, list):
        return homeworks
    raise TypeError(HOMEWORKS_TYPE_ERROR)


def parse_status(homework) -> str:
    """Получает статус домашней работы."""
    logging.debug(LOG_DEBUG_MESSAGE_PARSE_STATUS)

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if (not homework_name) or (not homework_status):
        raise KeyError(MISSING_KEY_ERROR_DICT)

    if homework_status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        return STATUS_CHANGE_MESSAGE.format(
            homework_name=homework_name, verdict=verdict
        )
    raise HomeworkStatusesException(STATUS_MISMATCH_ERROR)


def check_tokens() -> bool:
    """Проверяет наличие переменных окружения."""
    token_names = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    missing_tokens = []

    for token_name in token_names:
        if not globals().get(token_name):
            missing_tokens.append(token_name)

    if missing_tokens:
        missing_tokens_str = ', '.join(missing_tokens)
        logging.warning(MISSING_TOKENS_WARNING.format(
            missing_tokens=missing_tokens_str
        ))
        return False

    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(MISSING_ENV_VARS_ERROR)
        sys.exit(MISSING_ENV_VARS_ERROR)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    raised_error = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if not response:
                raise Exception(API_REQUEST_ERROR)
            check = check_response(response)
            if check:
                for homework in check:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logging.debug(NO_UPDATES_MESSAGE)

            current_timestamp = int(time.time())

        except SendMessageException:
            logging.error(SEND_MESSAGE_ERROR)
        except Exception as error:
            message = PROGRAM_FAILURE_MESSAGE.format(
                error=error,
                error_class=error.__class__
            )
            logging.error(message)
            new_error = str(error)
            if new_error != raised_error:
                send_message(bot, message)
                raised_error = new_error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    main()
