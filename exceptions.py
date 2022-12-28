class InvalidResponseCodeError(Exception):
    """Ошибка статуса"""
    pass


class TelegramSendError(Exception):
    """Ошибка отправки сообщений"""
    pass


class TokenError(Exception):
    """Ошибка в токенах."""
    pass
