import json

with open('coworker/data/coworker_config.json') as config_file:
    config = json.load(config_file)

# Prompts
system_sql = config['chat_prompts']['system_sql']
prompt_sql = config['chat_prompts']['prompt_sql']
system_summary = config['chat_prompts']['system_summary']
prompt_summary = config['chat_prompts']['prompt_summary']
system_error = config['chat_prompts']['system_error']

# Token limits
model_limit = config['token_limits']['model_limit']
sql_response_tokens = config['token_limits']['sql_response_tokens']
summary_response_tokens = config['token_limits']['summary_response_tokens']
error_response_tokens = config['token_limits']['error_response_tokens']