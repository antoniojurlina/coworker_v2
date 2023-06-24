class InvalidInputException(Exception):
    pass

class MissingAPIKeyException(InvalidInputException):
    pass

class RateLimitException(Exception):
    pass

class RequestException(Exception):
    def __init__(self, response):
        self.response = response

class ProgrammingErrorException(Exception):
    pass