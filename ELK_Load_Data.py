import cx_Oracle
# import oracledb
import pandas as pd
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
import pytz
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import importlib.util
import os
import requests
import multiprocessing

# Adjust number of workers based on CPU count
num_workers = min(8, multiprocessing.cpu_count() * 2)

load_dotenv()

# # Create a connection pool
# pool = oracledb.create_pool(
#     user=os.getenv('olap_prod_user_name'),
#     password=os.getenv('olap_prod_password'),
#     dsn=f"{os.getenv('olap_prod_host_address')}:{os.getenv('olap_prod_port')}/{os.getenv('olap_prod_service_name')}"
# )

# Set up the connection pool
pool = cx_Oracle.SessionPool(
    user=os.getenv('olap_prod_user_name'),
    password=os.getenv('olap_prod_password'),
    dsn=f"{os.getenv('olap_prod_host_address')}:{os.getenv('olap_prod_port')}/{os.getenv('olap_prod_service_name')}"
)

def fetch_value_list(query):
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchall()
            # Convert the result to a list
            return [row[0] for row in result]

def dynamic_import(module_name):
    current_dir = os.path.dirname(__file__)  # Get current directory
    module_path = os.path.join(current_dir, f"{module_name}.py")  # Construct file path

    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module  # Return the imported module


def create_es_connection():
    """Elastic Search Connection Establish"""
    print("CONNECTING TO ES.............")
    es = Elasticsearch(hosts=os.getenv('elk_host_address'), http_auth=(os.getenv('elk_user_name'),os.getenv('elk_password')), timeout=800, max_retries=10, retry_on_timeout=True)
    return es

def fetch_db_data(query,chunksize=100000):
    """Fetch data from DB in chunks"""
    print("FETCHING DATA..............")
    with pool.acquire() as connection:
        for chunk in pd.read_sql_query(query, connection, chunksize=chunksize):
            yield chunk

def bulk_insert_to_es(es, actions):
    """Bulk inserts data to Elasticsearch"""
    helpers.bulk(es, actions)

# Function to chunk the list
def chunk_list(data, chunk_size):
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

# Function to count documents using Elasticsearch API
def count_documents(es_url, index_name, field_name, values_chunk):
    url = f"{es_url}/{index_name}/_count"
    query = {
        "query": {
            "terms": {
                f"{field_name.upper()}.keyword": values_chunk
            }
        }
    }
    response = requests.post(url, json=query)
    if response.status_code == 200:
        return response.json().get("count", 0)
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return 0

def main(index_name,query_field):
    # Connection to Oracle DB and Elasticsearch
    start_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    print("Start time:", start_time.strftime('%Y-%m-%d %H:%M:%S'))

    module = dynamic_import(index_name)
    table_name = 'customer_load_rec'

    es = create_es_connection()
    if not es.indices.exists(index=index_name): # check index exist or not
        module.index_creation_in_elastic_search(es,index_name) # index creation in es
        print(f"Index {index_name} created in ES")

    query_value_list = f'select distinct {query_field} from {table_name}'
    query_field_value_list = fetch_value_list(query_value_list)

    print(query_value_list)
    print(f'Total {query_field} : ',len(query_field_value_list))

    total_elk_count = 0
    # Process the values in chunks
    for chunk in chunk_list(query_field_value_list, chunk_size=10000):
        count = count_documents(os.getenv('elk_host'),os.getenv('elk_port'), index_name, query_field, chunk)
        total_elk_count += count

    print(f"{index_name} - For {len(query_field_value_list)} {query_field}s Total document count in ELK : {total_elk_count}")

    batch_size = 10000
    count_rotation = 1
    offset_batch = 0
    for i in range(0, len(query_field_value_list), batch_size):
        print("Round - ",count_rotation)
        count_rotation += 1
        batch_list = query_field_value_list[i:i + batch_size]
        print('Batch size : ',len(batch_list))
        print('Batch list : ',batch_list[0],'.....',batch_list[-1])

        query = module.query
        query = "\n".join(query.strip().split("\n")[:-1]) # Removing last line where ETL_PROC_WID used for incremental
        table_alias = query.lower().split('from')[1].strip().split(' ')[1].strip() # fetch table alias like t101

        last_query_line = f"AND {table_alias}.{query_field} IN (select {query_field} from {table_name} OFFSET {offset_batch} ROWS FETCH NEXT {batch_size} ROWS ONLY)"
        offset_batch += batch_size
        query += "\n" + last_query_line

        total_count_query = f'SELECT COUNT(1) FROM ({query})'

        print('ESTIMATING TOTAL COUNT ON OLAP.....')
        total_count_df = module.fetch_db_data(total_count_query)
        print('TOTAL DATA COUNT =',total_count_df.iloc[0, 0])
        print("time:", datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S'))

        # Fetch, transform, and insert data in batches
        lot_count = 1
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for chunk in fetch_db_data(query):
                result = module.data_conversion(chunk)
                transformed_data = module.transform_new_data(index_name,result)
                print(lot_count," - ",len(transformed_data)," loading... time:", datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y %H:%M:%S'))
                lot_count += 1
                futures.append(executor.submit(bulk_insert_to_es, es, transformed_data))

            for future in as_completed(futures):
                future.result()  # Check for any exceptions

    es.indices.refresh(index=index_name)

    print("time:", datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S'))
    end_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    print("End time:", end_time.strftime('%Y-%m-%d %H:%M:%S'))
    print(f"Time taken: {(end_time - start_time).total_seconds():.2f} seconds")
    print("INDEXING COMPLETED")

if __name__ == '__main__':
    index_name = sys.argv[1]
    query_field = sys.argv[2]
    main(index_name,query_field)
