import tiktoken
import re
import json
from eod import EodHistoricalData

from coworker.exceptions.exceptions import ProgrammingErrorException
from coworker.modules.chat_completion import OpenAIChatCompletionModule
from coworker.modules.database_conn import DatabaseConnection
from coworker.modules.logging import Logger
from coworker.config.config import OPENAI_KEY, DB_HOST, DB_USER, DB_NAME, DB_PORT, DB_PASSWORD, EOD_KEY

class Coworker:
    def __init__(self):
        # Clients
        self.chat_completion = OpenAIChatCompletionModule(open_ai_key=OPENAI_KEY)
        self.database_conn = DatabaseConnection(
            host=DB_HOST, 
            port=DB_PORT, 
            user=DB_USER, 
            dbname=DB_NAME, 
            password=DB_PASSWORD
        )
        self.eod_client = EodHistoricalData(EOD_KEY)
        self.logger = Logger.get_instance(name="coworker_logger")

        # Data
        self.description_json = self._load_schema_json()
        self.companies_json = self._load_companies_json()
        self.model = 'gpt-4'
        self.prompt_sql = f'''
            \n
            Here is a schema available to you in PostgreSQL:
            {self._get_schema_description()}
            Write a PostgreSQL query to answer this request.

            You must remember the following:
            - If you are doing any comparisons make sure that you compare using ILIKE '%[string]%' instead of just `= [string]`.
            - If you are doing any division make sure that you avoid potential division by zero.
            - You are working with financial data. Weeks last only 5 days and the weekends are excluded.
        '''
        self.prompt_summary = f'''
            \n
            You are a financial analyst and someone just sent you this message. They want to know how you
            would do this.

            Ignoring  the fact that you do not actually have access to real-time data, 
            reply to them with a one or two sentence generic response assuming you have the following at your disposal:
                quarterly income statements, cash flow statements, balance sheets and daily share price data
        '''

        # Start with clean memories
        self._clear_cache_sql()
        self._clear_cache_summary()


    def _load_schema_json(self):
        with open('coworker/data/schema_description.json', 'r') as f:
            return json.load(f)
        
    def _load_companies_json(self):
        with open('coworker/data/companies.json', 'r') as f:
            return json.load(f)

    def _clear_cache_sql(self):
        self.sql_messages_cache = [{
            "role": "system", 
            "content": "You are a financial analyst in charge of writing SQL queries. Answer as concisely as possible. You must not truncate any SQL queries. You must return all queries wrapped with ```sql[SQL QUERY TEXT]```."
        }]
    
    def _clear_cache_summary(self):
        self.summary_messages_cache = [{
            "role": "system", 
            "content": "You are a finance expert. Answer as concisely as possible using only the information available to you in the prompt."
        }]

    def _handle_sql_messages_cache(self, request, max_response_tokens):
        if len(self.sql_messages_cache)==1:
            request += self.prompt_sql

        self.sql_messages_cache.append({"role": "user", "content": request})

        num_tokens = self._num_tokens_from_string(' '.join([dict['content'] for dict in self.sql_messages_cache]))

        while num_tokens + max_response_tokens > 8000:
            if len(self.sql_messages_cache) > 1:
                num_tokens -= self._num_tokens_from_string(self.sql_messages_cache[1]["content"])
                self.sql_messages_cache.pop(1)
                if self.sql_messages_cache[1]["role"] == "assistant":
                    self.sql_messages_cache[2]["content"] += self.prompt_sql
            else:
                break
    
    def _handle_summary_messages_cache(self, request, max_response_tokens):
        if len(self.summary_messages_cache)==1:
            request += self.prompt_summary
        
        self.summary_messages_cache.append({"role": "user", "content": request})

        num_tokens = self._num_tokens_from_string(' '.join([dict['content'] for dict in self.summary_messages_cache]))

        while num_tokens + max_response_tokens > 8000:
            if len(self.summary_messages_cache) > 1:
                num_tokens -= self._num_tokens_from_string(self.summary_messages_cache[1]["content"])
                self.summary_messages_cache.pop(1)
                if self.summary_messages_cache[1]["role"] == "assistant":
                    self.summary_messages_cache[2]["content"] += self.prompt_summary
            else:
                break

    def _get_schema_description(self):
        result = []

        result.append("Tables:")
        for table in self.description_json['tables']:
            fields = [column['name'] for column in table['columns']]
            result.append(f'  - "{table["name"]}" with the fields: {", ".join(fields)}')

        result.append("\nViews:")
        for view in self.description_json['views']:
            fields = [column['name'] for column in view['columns']]
            result.append(f'  - "{view["name"]}" with the fields: {", ".join(fields)}')

        result.append("\nFunctions:")
        for function in self.description_json['functions']:
            result.append(f'  - {function["description"]}')

        return '\n'.join(result)
    
    def _num_tokens_from_string(self, string: str) -> int:
        '''Returns the number of tokens in a text string.'''
        encoding = tiktoken.encoding_for_model(self.model)
        num_tokens = len(encoding.encode(string))
        return num_tokens

    async def message_chatgpt(self, messages, max_tokens=4000):
        return await self.chat_completion.message_chatgpt(messages=messages, model=self.model, max_tokens=max_tokens)

    async def _fetch_data_with_retry(self, query, n=3):
        for _ in range(n):
            try:
                return self.database_conn.fetch_data(query)
            except ProgrammingErrorException as error:
                self.logger.log_error(error=error)
                error_message = f'''
                How can I fix the following error?
                PostgreSQL query:
                {query}
                Error:
                {error}
                Available schema:
                {self._get_schema_description()}
                '''
                messages = [
                    {"role": "system", "content": "You are an expert SQL writer in charge of debugging SQL queries. You must not truncate any SQL queries. You must return all queries wrapped with ```sql[SQL QUERY TEXT]```."},
                    {"role": "user", "content": error_message}
                ]

                answer = await self.message_chatgpt(messages=messages)
                query = self._extract_query(answer)

                self.logger.log_sql_query(sql_query=query)
        return None

    def _extract_query(self, answer):
        start = "```sql"
        end = "```"
        start_index = answer.find(start)
        end_index = answer.find(end, start_index + len(start))
        if start_index != -1 and end_index != -1:
            query = answer[start_index + len(start):end_index].strip()
            if query:
                return query

        # Extract using regular SQL patterns if the initial extraction is empty
        pattern = re.compile(r'\b(SELECT|WITH)\b.*?;\s*$', re.IGNORECASE | re.DOTALL)
        match = pattern.search(answer)
        if match:
            return match.group()
            
        return None
    
    def _process_summary(self, answer_summary):
        phrases_to_check = ["unfortunately", "an ai", "sorry", "language model", "cannot"]
        lower_answer_summary = answer_summary.lower()
        for phrase in phrases_to_check:
            if phrase in lower_answer_summary:
                return "Sure! Here is the data you requested."
        return answer_summary
    
    async def get_info_from_text(self, request: str):
        text = re.sub('[^A-Za-z0-9& ]+', '', request)  # remove special characters
        words_company = [word for word in text.split(' ') if len(word) >= 4]
        words_ticker = [word for word in text.split(' ') if len(word) >= 2]
        
        tickers = []
        for word in words_company:
            for company, ticker in self.companies_json.items():
                if word.lower() in company.lower():
                    if ticker not in tickers:  # to avoid duplicate entries
                        tickers.append(ticker)
        
        for word in words_ticker:
            for company, ticker in self.companies_json.items():
                if word == ticker:
                    if ticker not in tickers:  # to avoid duplicate entries
                        tickers.append(ticker)
        
        if not tickers:
            return None

        info_dict = {
            'Code': [],
            'Name': [],
            'Exchange': [],
            'CurrencyCode': [],
            'Sector': [],
            'Industry': [],
            'Description': [],
            'CEO': [],
            'IPODate': [],
            'Country': [],
            'City': []
        }

        for ticker in tickers:
            info = self.eod_client.get_fundamental_equity(ticker, filter_='General')
            
            info_dict['Code'].append(info['Code'])
            info_dict['Name'].append(info['Name'])
            info_dict['Exchange'].append(info['Exchange'])
            info_dict['CurrencyCode'].append(info['CurrencyCode'])
            info_dict['Sector'].append(info['Sector'])
            info_dict['Industry'].append(info['Industry'])
            info_dict['Description'].append(info['Description'])
            info_dict['CEO'].append(info['Officers']['0'])
            info_dict['IPODate'].append(info['IPODate'])
            info_dict['Country'].append(info['AddressData']['Country'])
            info_dict['City'].append(info['AddressData']['City'])

        return info_dict

    async def generate_summary(self, request: str):
        if "thank you" in request.lower():
            self._clear_cache_sql()
            self._clear_cache_summary()
            return "You're welcome!"

        self._handle_sql_messages_cache(request, max_response_tokens=4000)
        self._handle_summary_messages_cache(request, max_response_tokens=2000)

        answer_summary = await self.message_chatgpt(messages=self.summary_messages_cache, max_tokens=2000)
        summary = self._process_summary(answer_summary)

        self.summary_messages_cache.append({"role": "assistant", "content": summary})

        return summary

    async def process_query_and_data(self, request: str):
        self._handle_sql_messages_cache(request, max_response_tokens=4000)

        answer_sql = await self.message_chatgpt(messages=self.sql_messages_cache, max_tokens=4000)

        query = self._extract_query(answer_sql)
        data = await self._fetch_data_with_retry(query=query)

        self.logger.log_sql_query(sql_query=query)
        self.sql_messages_cache.append({"role": "assistant", "content": query})

        if data is not None:
            return query, data
        else:
            return None, 'Apologies. I cannot figure out a way to answer this request.'

