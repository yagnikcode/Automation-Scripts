import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

def fail_function(context):
    project_name = "MES"
    fail_task = context['task'].task_id
    dag_name = context['task'].dag_id
    sub = f"Failed_job {project_name} - {dag_name} at {fail_task}"
    MESSAGE_BODY = f'Dear TEAM,\n\n----- {project_name} Failed Job Status -----\n\nFAILED Task : {fail_task}\nDAG Name : {dag_name}\n\n\nRegards,\nATC TEAM'
    msg = MIMEMultipart()
    body_part = MIMEText(MESSAGE_BODY, 'plain')
    msg['Subject'] = sub
    msg['From'] = os.getenv('MAIL_FROM_LIST')
    recipients = os.getenv('ATC_MAIL_LIST').split(',')
    msg.attach(body_part)
    smtpObj = smtplib.SMTP(os.getenv("SMTP_SERVER_IP"))
    smtpObj.sendmail(msg['From'], recipients, msg.as_string())
    smtpObj.quit()

def success_function(context):
    project_name = "MES"
    success_task = context['task'].task_id
    dag_name = context['task'].dag_id
    sub = f"Success_job {project_name} - {dag_name} at {success_task}"
    MESSAGE_BODY = f'Dear TEAM,\n\n----- {project_name} Success Job Status -----\n\nSuccess Task : {success_task}\nDAG Name : {dag_name}\n\n\nRegards,\nATC TEAM'
    msg = MIMEMultipart()
    body_part = MIMEText(MESSAGE_BODY, 'plain')
    msg['Subject'] = sub
    msg['From'] = os.getenv('MAIL_FROM_LIST')
    recipients = os.getenv('ATC_MAIL_LIST').split(',')
    msg.attach(body_part)
    smtpObj = smtplib.SMTP(os.getenv("SMTP_SERVER_IP"))
    smtpObj.sendmail(msg['From'], recipients, msg.as_string())
    smtpObj.quit()  
