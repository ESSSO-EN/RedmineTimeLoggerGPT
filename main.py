import openai
import sys
import json
import os

from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError, ResourceSetIndexError
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load default environment variables (.env)
load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
assert OPENAI_API_KEY, "OPENAI_API_KEY environment variable is missing from .env"
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")
assert REDMINE_API_KEY, "REDMINE_API_KEY environment variable is missing from .env"

# OpenAI Model configuration
OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL", "gpt-3.5-turbo")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", 0.0))

# Redmine configuratino
REDMINE_URL = os.getenv("REDMINE_URL", "")
assert REDMINE_URL, "REDMINE_URL environment variable is missing from .env"

def timelogger_agent(message):
    # set openai key
    openai.api_key = OPENAI_API_KEY
    # initialize list to store conversation with agent
    messages = []
    # set the role of agent
    system_msg = "You will help me breakdown my work time hours as an assistant."
    messages.append({"role": "system", "content": system_msg})
    #print('messages:{}'.format(messages))
    
    # give prompt to the agent
    messages.append({"role": "user", "content": message})

    # specify date context so agent knows correct current date and timezone
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    message = "For context today's date is {}".format(now)
    messages.append({"role": "user", "content": message})

    # agent introduction and append message for context of the whole session
    message = input("Hi I am your new agent, what can do you want me to log?\n")
    messages.append({"role": "user", "content": message})
    
    # actual chatgpt call
    response = openai.ChatCompletion.create(
       model=OPENAI_API_MODEL,
       temperature=OPENAI_TEMPERATURE,
       messages=messages)
    reply = response["choices"][0]["message"]["content"]
    messages.append({"role": "assistant", "content": reply})
    print("\n" + reply + "\n")
    
    try:
        my_list = json.loads(reply)
        print('************************************')
        for my_dict in my_list:
            issue_id = my_dict["issue_id"]
            activity_id = my_dict["activity_id"]
            hours = my_dict["hours"]
            spent_on = my_dict["spent_on"]

            print('issue_id:{}'.format(issue_id))
            print('activity_id:{}'.format(activity_id))
            print('hours:{}'.format(hours))
            print('spent_on:{}'.format(spent_on))
            print('************************************')
    except:
        return

    confirm = input('Proceed to log this (Y/N)?')
    if confirm.strip().upper() == 'Y':
        try:
            # get_ticket_detail(issue_id)
            redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)
            
            # get redmine current userid
            current_user_id = redmine.user.get('me').id

            # loop the list and log the breakdown to redmine
            for my_dict in my_list:
                issue_id = my_dict["issue_id"]
                activity_id = my_dict["activity_id"]
                hours = my_dict["hours"]
                spent_on = my_dict["spent_on"]

                time_entry = redmine.time_entry.new()
                time_entry.issue_id = issue_id
                time_entry.spent_on = spent_on
                time_entry.hours = hours
                time_entry.activity_id = activity_id
                time_entry.save()

                # verify if saved
                time_entries = redmine.time_entry.filter(user_id=current_user_id, issue_id=issue_id, limit=1, from_date=spent_on, to_date=spent_on)
                print(f'Successfully logged issue:{time_entries[0].issue}, hours:{time_entries[0].hours}, spent_on:{time_entries[0].spent_on}')


        except (ResourceNotFoundError):
            print ('Not found')
        except (ResourceSetIndexError):
            print ('Log not found')
    else:
        print('Logging aborted.')


if __name__ == "__main__":
    # get prompt from txt file
    filename = "./chatgpt-prompt.txt"
    with open(filename, "r") as file:
        content=file.read()
        #print(content)
    # execute the agent
    timelogger_agent(str(content))