import logging
from logging.handlers import TimedRotatingFileHandler
import datetime

class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name=None):
        if not hasattr(self, 'logger'):
            today = datetime.date.today().strftime('%Y-%m-%d')
            log_file = f"/Users/antoniojurlina/Coworker/data/logging/{today}_conversation_history.log"

            self.logger = logging.getLogger(name)
            self.logger.setLevel(logging.INFO)

            handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @classmethod
    def get_instance(cls, name):
        return cls(name)

    def log_error(self, error):
        self.logger.error(error)

    def log_warning(self, warning):
        self.logger.warning(warning)

    def log_gpt_prompt(self, prompt):
        self.logger.info(f"GPT Prompt:\n{prompt}")

    def log_gpt_response(self, response):
        self.logger.info(f"GPT Response:\n{response}")

    def log_finish_reason(self, finish_reason):
        self.logger.info(f"GPT API Finish Reason: {finish_reason}")

    def log_sql_query(self, sql_query):
        self.logger.info(f"SQL Query:\n{sql_query}")