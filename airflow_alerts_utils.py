import requests
import os
 
def success_function(context):
    project_name = 'PV'
    success_task = context['task'].task_id
    dag_name = context['task'].dag_id
    sub = f"Success_job {project_name} - {dag_name} at {success_task}"
    url = os.getenv("TEAMS_ALERT_URL")
    message = sub
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "text": message
    }
    return requests.post(url, headers=headers, json=payload)
 
 
def fail_function(context):
    project_name = 'PV'
    fail_task = context['task'].task_id
    dag_name = context['task'].dag_id
    sub = f"Failed_job {project_name} - {dag_name} at {fail_task}"
    url = os.getenv("TEAMS_ALERT_URL")
    message = sub
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "text": message
    }
    return requests.post(url, headers=headers, json=payload)
