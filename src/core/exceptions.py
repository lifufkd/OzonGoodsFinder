

class AppException(Exception):
    def __init__(self, detail: str | None = None):
        self.detail = detail


class TgPermissionsError(AppException):
    def __init__(self, detail: str):
        super().__init__(detail)


class TgChatIdInvalid(AppException):
    def __init__(self, detail: str):
        super().__init__(detail)


class TgChatTopicIdInvalid(AppException):
    def __init__(self, detail: str):
        super().__init__(detail)


class ProxyError(AppException):
    def __init__(self, detail: str | None = None):
        super().__init__(detail)
