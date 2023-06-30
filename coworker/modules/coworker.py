import tiktoken
import re
import json
from eod import EodHistoricalData

from coworker.exceptions.exceptions import ProgrammingErrorException
from coworker.modules.chat_completion import OpenAIChatCompletionModule
from coworker.modules.database_conn import DatabaseConnection
from coworker.modules.logging import Logger
from coworker.config.keys import OPENAI_KEY, DB_HOST, DB_USER, DB_NAME, DB_PORT, DB_PASSWORD, EOD_KEY
from coworker.config.config import system_sql, prompt_sql, system_summary, prompt_summary, system_error
from coworker.config.config import model_limit, sql_response_tokens, summary_response_tokens, error_response_tokens

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
        self.system_sql = system_sql
        self.prompt_sql = prompt_sql + self._get_schema_description()
        self.system_summary = system_summary
        self.prompt_summary = prompt_summary
        self.system_tokens = max(
            self._num_tokens_from_string(self.system_sql),
            self._num_tokens_from_string(self.system_summary)
        )
        self.prompt_tokens = max(
            self._num_tokens_from_string(self.prompt_sql),
            self._num_tokens_from_string(self.prompt_summary)
        )

    def _load_schema_json(self):
        with open('coworker/data/schema_description.json', 'r') as f:
            return json.load(f)
        
    def _load_companies_json(self):
        with open('coworker/data/companies.json', 'r') as f:
            return json.load(f)
        
    def _num_tokens_from_string(self, string: str) -> int:
        '''Returns the number of tokens in a text string.'''
        encoding = tiktoken.encoding_for_model(self.model)
        num_tokens = len(encoding.encode(string))
        return num_tokens

    def _process_message_history(self, message_history, max_response_tokens, history_type):
        # Get prompts and token limits
        prompt_tokens = self.prompt_tokens
        system_tokens = self.system_tokens

        if history_type == 'sql':
            system_content = self.system_sql
            prompt = self.prompt_sql
        if history_type == 'summary':
            system_content = self.system_summary
            prompt = self.prompt_summary
        
        limit = model_limit - prompt_tokens - system_tokens - max_response_tokens

        num_tokens = 0
        new_history = []
        
        # Process messages from the end to the beginning
        for message in reversed(message_history):
            if history_type == 'sql':
                if message['role'] == 'user':
                    new_content = self._faang_handling(message["content"], replacement_type='company')
                else:
                    new_content = message['content']
            else:
                if message['role'] == 'user':
                    new_content = 'Boss[cheerily, professional tone]: I need your help with another data lookup.' + message['content'] + '\nYou[after reviewing quarterly income statements, cash flow statements, balance sheets, daily share price data]: Attached is the data you were looking for. What I did was'
                else:
                    new_content = message['content']

            message_tokens = self._num_tokens_from_string(new_content)

            # If adding this message would exceed the limit, stop processing
            if num_tokens + message_tokens > limit:
                break

            num_tokens += message_tokens

            # Add the current message to the beginning of new_history
            new_history.insert(0, {"role":message['role'], "content":new_content})
        
        # find the oldest possible message with the role "user" and add the prompt string variable to the content
        for message in new_history:
            if message['role'] == 'user':
                if history_type == 'sql':
                    message['content'] += prompt
                if history_type == 'summary':
                    message['content'] = prompt + message['content']
                break

        # Return the new message history with the system message at the beginning
        return [{"role": "system", "content": system_content}] + new_history

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
    
    def _faang_handling(self, request, replacement_type):
        if replacement_type == 'ticker':
            replacement_text = 'META AAPL AMZN NFLX GOOG'
        if replacement_type == 'company':
            replacement_text = 'Meta, Apple, Amazon, Netflix and Alphabet'
        pattern = re.compile(r'\bFAANG\b', re.IGNORECASE)
        return pattern.sub(replacement_text, request)

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
        # remove numbers, %, $
        cleaned_answer_summary = re.sub(r'\d+|%|\$', '', answer_summary)
        return cleaned_answer_summary
    
    async def message_chatgpt(self, messages, max_tokens):
        return await self.chat_completion.message_chatgpt(messages=messages, model=self.model, max_tokens=max_tokens)

    async def _fetch_data_with_retry(self, query, n=3):
        for _ in range(n):
            try:
                # Attempt to fetch the data
                data = self.database_conn.fetch_data(query)
                # If successful, return the data immediately and exit the loop
                return data
            except ProgrammingErrorException as error:
                # Log the error
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
                    {"role": "system", "content": system_error},
                    {"role": "user", "content": error_message}
                ]

                # Generate a new query
                answer = await self.message_chatgpt(messages=messages, max_tokens=error_response_tokens)
                query = self._extract_query(answer)

                # Log the new query
                self.logger.log_sql_query(sql_query=query)
        
        # If we've exhausted our retries and haven't returned, we've failed to fetch the data
        return None
    
    async def get_info_from_text(self, message_history):
        # find the newest possible message with the role "user"
        for message in reversed(message_history):
            if message['role'] == 'user':
                request = message['content']
                break

        text = self._faang_handling(request, replacement_type='ticker')
        text = re.sub('[^A-Za-z0-9& ]+', ' ', text)  # remove special characters

        words_company = [word for word in text.split(' ') if len(word) >= 4]
        words_ticker = [word for word in text.split(' ') if len(word) >= 2]
        
        tickers = []
        if words_company:
            for word in words_company:
                for company, ticker in self.companies_json.items():
                    if word.lower() in company.lower():
                        if ticker not in tickers:  # to avoid duplicate entries
                            tickers.append(ticker)
        
        if words_ticker:
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

    async def generate_summary(self, message_history, response_tokens=summary_response_tokens):
        messages = self._process_message_history(message_history, 
                                                 max_response_tokens=response_tokens, 
                                                 history_type='summary')

        answer_summary = await self.message_chatgpt(messages=messages, max_tokens=response_tokens)
        summary = self._process_summary(answer_summary)

        return summary

    async def process_query_and_data(self, message_history, response_tokens=sql_response_tokens):
        messages = self._process_message_history(message_history, 
                                                 max_response_tokens=response_tokens, 
                                                 history_type='sql')

        answer_sql = await self.message_chatgpt(messages=messages, max_tokens=response_tokens)

        query = self._extract_query(answer_sql)
        data = await self._fetch_data_with_retry(query=query)

        self.logger.log_sql_query(sql_query=query)

        if data is not None:
            return query, data
        else:
            return None, 'Apologies. I cannot figure out a way to answer this request.'