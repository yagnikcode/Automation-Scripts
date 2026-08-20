import requests
from datetime import datetime,timedelta
import pytz
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
db_credential = {
    "host_address" : os.getenv('olap_prod_host_address'),
    "port" : os.getenv('olap_prod_port'),
    "service_name" : os.getenv('olap_prod_service_name'),
    "user_name" : os.getenv('olap_prod_user_name'),
    "password" : os.getenv('olap_prod_password')
}

es_credential = {
    "host_address": os.getenv('elk_host_address'),
    "user_name": os.getenv('elk_user_name'),
    "password": os.getenv('elk_password'),
    "host_address_customer" : os.getenv('elk_host_address_customer'),
    "port_customer" : os.getenv('elk_port_customer')
}

automate_url = {
    "power_automate_url" : os.getenv('power_automate_url')
}

# Fetch data counts for today
def fetch_data_count(today_date):
    today_date = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y')
    file_name = f'data_count_{today_date}.csv'
    try:
        df = pd.read_csv(file_name,header=None)
        rows = df.values.tolist()
        return rows
    except:
        print(f"Data not available in {file_name}")
        raise SystemExit


if __name__ == '__main__':
    today_date = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y')

    data = fetch_data_count(today_date)
    html_content = f"""
    <html>
        <body>
            <p style="font-size: 16px;">
                <b>DATA COUNT on {today_date}</b>
            </p>
            <table border="1">
                <thead>
                    <tr>
                        <th>RECORD_DATE</th>
                        <th>ELK_INDEX_NAME</th>
                        <th>TOTAL_COUNT</th>
                    </tr>
                </thead>
                <tbody>
            """
    for i in data:
        html_content += f"""
                    <tr>
                """
        for v in i:
            html_content += f"""
                        <td>{v}</td>
                    """
        html_content += f"""
                    </tr>
                """
            
    html_content += """
                </tbody>
            </table>
        </body>
    </html>
    """

    # Power Automate Flow URL
    power_automate_url = automate_url['power_automate_url']

    payload = {
        "html_content": html_content
    }

    # Send data to Power Automate
    headers = {"Content-Type": "application/json"}
    response = requests.post(power_automate_url, headers=headers, json = payload)

    yesterday_date = (datetime.now(pytz.timezone('Asia/Kolkata')) - timedelta(days=1)).strftime('%d-%m-%Y')
    old_file_name = f'data_count_{yesterday_date}.csv'
    try:
        os.remove(old_file_name)
        print(f"File {old_file_name} has been deleted.")
    except FileNotFoundError:
        print(f"The file {old_file_name} does not exist.")

