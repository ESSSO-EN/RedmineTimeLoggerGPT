# RedmineTimeLoggerGPT
A simple time logger utilizing OpenAI's ChatGPT and integrates with Redmine.
The time logger agent will accept the details about the ticket you have worked on
and automatically logged the details into Redmine.
This tool do not have UI and you will input the details of your work in free form natural language
after which ChatGPT analyzes it and breaks it down for you prior to logging it to Redmine.

Sample prompt:
I have completed coding today for ticket 8888 and spent 3 hours.
Last Wednesday I worked on testing ticket 7777 and did 2.5 hours.

Timelogger Agent breaks it down for you. Then formats it into a list of dictionary and logs it to Redmine:
[{"issue_id":"8888", "activity_id"="9", "hours":"3", "spent_on":"2023/04/28"}]
[{"issue_id":"7777", "activity_id"="10", "hours":"2.5", "spent_on":"2023/04/26"}]


The code is not yet refactored. 
This is the initial use case which popped into my mind while checking out the excitement sorrounding around this cool tech chatGPT and the overall AI/LLM ecosystem. 
This is just a simple tool which helps me at work at this time, but I do have plans on adding features bit by bit.
