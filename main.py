import openai
import sys
import json
import os
import pinecone
import time
import re

from redminelib import Redmine
from redminelib.exceptions import ResourceNotFoundError, ResourceSetIndexError
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from uuid import uuid4


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

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
assert PINECONE_API_KEY, "PINECONE_API_KEY environment variable is missing from .env"

PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "")
assert (
    PINECONE_ENVIRONMENT
), "PINECONE_ENVIRONMENT environment variable is missing from .env"

TABLE_NAME = os.getenv("TABLE_NAME", "")
assert TABLE_NAME, "TABLE_NAME environment variable is missing from .env"

# Configure OpenAI and Pinecone
openai.api_key = OPENAI_API_KEY
pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)

# Create Pinecone index
table_name = TABLE_NAME
dimension = 1536
metric = "cosine"
pod_type = "p1"
# check if index already exists (only create index if not)
if table_name not in pinecone.list_indexes():
            print(f"\nInitializing assistant's memory...")
            pinecone.create_index(
                table_name, dimension=dimension, metric=metric, pod_type=pod_type
            )
else:
    print(f"\nLoading info into assistant's memory...")
    time.sleep(3)  # Sleep for some time

# Connect to the index
index = pinecone.Index(table_name)

def delete_namespace(namespace):
    index.delete(delete_all=True, namespace=namespace)

def gpt_embedding(content, engine='text-embedding-ada-002'):
    """
    Get embedding for the text

    Args:
        content (str):
        engine (str): 

    Returns:
        vector: a normal list

    """
    # fix any UNICODE errors
    #content= content.encode(encoding='ASCII', errors='ignore').decode()
    response=openai.Embedding.create(input=content, engine=engine)
    vector=response['data'][0]['embedding']
    return vector

def openai_call(
    messages,
    model: str = OPENAI_API_MODEL,
    temperature: float = OPENAI_TEMPERATURE
):
    while True:
        try:
            # Use chat completion API
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except openai.error.RateLimitError:
            print(
                "   *** The OpenAI API rate limit has been exceeded. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        except openai.error.Timeout:
            print(
                "   *** OpenAI API timeout occured. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        except openai.error.APIError:
            print(
                "   *** OpenAI API error occured. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        except openai.error.APIConnectionError:
            print(
                "   *** OpenAI API connection error occured. Check your network settings, proxy configuration, SSL certificates, or firewall rules. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        except openai.error.InvalidRequestError:
            print(
                "   *** OpenAI API invalid request. Check the documentation for the specific API method you are calling and make sure you are sending valid and complete parameters. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        except openai.error.ServiceUnavailableError:
            print(
                "   *** OpenAI API service unavailable. Waiting 10 seconds and trying again. ***"
            )
            time.sleep(10)  # Wait 10 seconds and try again
        else:
            break

def timelogger_agent(system_message):
    # set openai key
    openai.api_key = OPENAI_API_KEY
    
    # initialize list to retrieve objective of agent
    messages = []
    prompt = "What is your objective as an assistant?"
    vector = gpt_embedding(prompt)
    result = index.query(vector=vector, top_k=3, namespace="Objective", include_metadata=True)
    if result['matches']:
        matches = result['matches']
        # get list of retrieved text
        messages.append({"role": "system", "content": matches[0]['metadata']['content']})
        messages.append({"role": "user", "content": matches[1]['metadata']['content']})
    else:
        objective_load = list()
        # set the role of agent
        messages.append({"role": "system", "content": system_message})
        #print('system_message:{}'.format(system_message))
      
        # specify date context so agent knows correct current date and timezone
        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        time_context = "For context today's date is {}".format(now)
        messages.append({"role": "user", "content": time_context})
        
        unique_id = str(uuid4())
        objective_load.append((unique_id, vector, messages[0]))
        unique_id = str(uuid4())
        objective_load.append((unique_id, vector, messages[1]))
        index.upsert(objective_load, namespace="Objective")
    
    # Get task list and append into messages
    vector = gpt_embedding("task list")
    result = index.query(vector=vector, top_k=1, namespace="Task List 1", include_metadata=True)
    if result['matches']:
        matches = result['matches']
        # get list of retrieved text
        contexts = [item['metadata']['content'] for item in result['matches']]
        messages.append({"role": "assistant", "content": contexts[0]})

    # Set objective of agent
    openai_call(messages)
    
    print("\033[95m\033[1m"+ "\nAssistant: " + "\033[0m\033[0m" + "How can I help you today?")

    # initialize list to store conversation with agent
    while True:
        prompt = input("\033[95m\033[1m" + "\nYou: " + "\033[0m\033[0m")

        if prompt.lower() == "quit":
            payload = list()
            
            print("\nStoring info into assistant's memory...")
            messages.append({"role": "user", "content": "Please give my task list"})
            response = openai_call(messages)
            
            # Insert task list into picone
            vector=gpt_embedding(response)
            index.delete(ids=["Task"])
            payload.append(("Task", vector, {"role": "assistant", "content": response}))
            index.upsert(payload, namespace="Task List 1")    
            break
          

        messages.append({"role": "user", "content": prompt})
        response = openai_call(messages)
        messages.append({"role": "assistant", "content": response})
        print("\033[95m\033[1m" + "\nAssistant: " + "\033[0m\033[0m" + response + "\n")

        if re.search('\[\{.*\}\]' ,response):
            # get_ticket_detail(issue_id)
            redmine = Redmine(REDMINE_URL, key=REDMINE_API_KEY)

            try:
                my_list = json.loads(re.findall('\[\{.*\}\]' ,response)[0])
                print('************************************')
                for my_dict in my_list:
                    issue_id = my_dict["issue_id"]
                    activity_id = my_dict["activity_id"]
                    hours = my_dict["hours"]
                    spent_on = my_dict["spent_on"]

                    task = redmine.isssue.get(issue_id)

                    print(f'issue_id:{issue_id} ({task.subject})')
                    print(f'activity_id:{activity_id} (9:開発作業), 12:調査・検討, 14:会議・レビュー・指導')
                    print(f'hours:{hours}')
                    print(f'spent_on:{spent_on}')
                    print('************************************')
            except Exception as err:
                print(f"Error has occured. {err}")
                return err

            # REDMINE FROM HERE
            confirm = input("\033[95m\033[1m" + "Assistant: Proceed to log this (Y/N)?" + "\033[0m\033[0m")
            if confirm.strip().upper() == 'Y':
                try:    
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
    #delete_namespace("Task List 1")
    #delete_namespace("Objective")