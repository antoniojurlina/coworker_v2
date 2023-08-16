# coworker_v2
Fast and awesome.

This is my project for allowing GPT4 to query the publicly traded company data from the SEC (residing in a SQL database). 

It uses very little additional library overhead, and implements a parallel memory for the bot, with asynchronous API calls to GPT. This way one API call can be in charge of getting the correct SQL and another in charge of providing a text summary of the results. The whole process is quite fast (~15 seconds per request), compared to the libraries like langchain.

main.py enables several endpoints for the frontend (which does not exist yet) to communicate with the GPT bot.

The test_notebook.ipynb file is designed in such a way to enable the testing of the asynchronous API calls and the wait times the user could expect in the frontend part of a potential future app.
