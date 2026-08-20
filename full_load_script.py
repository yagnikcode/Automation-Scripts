# import cx_Oracle
import oracledb
import pandas as pd
from elasticsearch import Elasticsearch, helpers
from datetime import datetime, timezone
import pytz
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import importlib.util
import os
import multiprocessing

# Adjust number of workers based on CPU count
num_workers = min(8, multiprocessing.cpu_count() * 2)

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
    "password": os.getenv('elk_password')
}

def dynamic_import(module_name):
    current_dir = os.path.dirname(__file__)  # Get current directory
    module_path = os.path.join(current_dir, f"{module_name}.py")  # Construct file path
    
    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module  # Return the imported module

# Create a connection pool
pool = oracledb.create_pool(
    user=db_credential['user_name'],
    password=db_credential['password'],
    dsn=f"{db_credential['host_address']}:{db_credential['port']}/{db_credential['service_name']}"
)


# # Set up the connection pool
# pool = cx_Oracle.SessionPool(
#     user=db_credential['user_name'],
#     password=db_credential['password'],
#     dsn=f"{db_credential['host_address']}:{db_credential['port']}/{db_credential['service_name']}"
# )

# Create Database connection and Fetch Query Data
def fetch_db_data(query,chunksize=100000):
    """Fetch data from DB in chunks"""
    print("FETCHING DATA..............")
    with pool.acquire() as connection:
        for chunk in pd.read_sql_query(query, connection, chunksize=chunksize):
            yield chunk


def create_es_connection(es_credential):
    """Elastic Search Connection Establish"""
    print("CONNECTING TO ES.............")
    es = Elasticsearch(hosts=es_credential['host_address'], http_auth=(es_credential['user_name'],es_credential['password']), timeout=800, max_retries=10, retry_on_timeout=True)
    return es


# def get_db_data(query, conn, chunksize=100000):
#     """Fetch data from DB in chunks"""
#     for chunk in pd.read_sql_query(query, conn, chunksize=chunksize):
#         yield chunk

def bulk_insert_to_es(es, actions):
    """Bulk inserts data to Elasticsearch"""
    helpers.bulk(es, actions)


def main(index_name,original_index_name):
    # Connection to Oracle DB and Elasticsearch
    start_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    print("Start time:", start_time.strftime('%Y-%m-%d %H:%M:%S'))

    module = dynamic_import(original_index_name)
    query = module.query
    query = "\n".join(query.strip().split("\n")[:-1]) # Removing last line where ETL_PROC_WID used for incremental

    total_count_query = f'SELECT COUNT(1) FROM ({query})'

    # conn = database_connection(db_credential)
    es = create_es_connection(es_credential)

    # print('ESTIMATING TOTAL COUNT.....')
    # total_count_df = module.fetch_db_data(total_count_query)
    # print('TOTAL DATA COUNT =',total_count_df.iloc[0, 0])
    # print("time:", datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S'))

    if not es.indices.exists(index=index_name): # check index exist or not
        module.index_creation_in_elastic_search(es,index_name) # index creation in es
    
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
    original_index_name = sys.argv[1]
    # full_load_index_name = sys.argv[1] + '_full_load'
    full_load_index_name = original_index_name
    main(full_load_index_name,original_index_name)
