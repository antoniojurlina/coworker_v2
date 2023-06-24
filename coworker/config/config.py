import os
from dotenv import load_dotenv

# Load envirnoment variables from .env file
load_dotenv()

# Access the environment variables
OPENAI_KEY=os.getenv('OPENAI_KEY')
DB_HOST=os.getenv('DB_HOST')
DB_USER=os.getenv('DB_USER')
DB_NAME=os.getenv('DB_NAME')
DB_PORT=os.getenv('DB_PORT')
DB_PASSWORD=os.getenv('DB_PASSWORD')

