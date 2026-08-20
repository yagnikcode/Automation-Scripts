from elasticsearch import Elasticsearch, helpers
import oracledb
from concurrent.futures import ThreadPoolExecutor
import os
from datetime import datetime
import pytz
import multiprocessing
from dotenv import load_dotenv
import requests
from tqdm import tqdm

load_dotenv()

# ONLY EDIT BELOW 3 inputs
##########################################################
INDEX_NAME = "asset_data"
UNIQUE_ID = 'src_row_id'
TABLE_NAME = "customer_unique_id_" + INDEX_NAME
##########################################################


# Config
ES_HOST = os.getenv("elk_host_address")
ORACLE_USER = os.getenv("olap_prod_user_name")
ORACLE_PWD = os.getenv("olap_prod_password")
ORACLE_DSN = oracledb.makedsn(f"{os.getenv('olap_prod_host_address')}", 1521, service_name=f"{os.getenv('olap_prod_service_name')}")
# ORACLE_DSN = "host:port/service"
THREADS = min(8, multiprocessing.cpu_count() * 2)
SLICE_COUNT = THREADS
BATCH_SIZE = 10000
ES_AUTH = (os.getenv('elk_user_name'), os.getenv('elk_password'))

# Connect to Oracle
pool = oracledb.create_pool(user=ORACLE_USER, password=ORACLE_PWD, dsn=ORACLE_DSN, min=1, max=THREADS, increment=1, expire_time=60)

TOTAL_ID_COUNT = int(requests.post(f"{ES_HOST}/{INDEX_NAME}/_count", json={"query": {"match_all": {}}}).json()['count'])
TOTAL_IDS_PER_SLICE = TOTAL_ID_COUNT // SLICE_COUNT
bar_format = (
    "{desc}: |{bar}| {percentage:.1f}% "
    "[{n_fmt}/{total_fmt} ids, "
    "Elapsed: {elapsed}, "
    "Remaining: {remaining}, "
    "Rate: {rate_fmt}/s]"
)

def create_db_table():
    # Create table in DB if not exist
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name = UPPER(:1)", [TABLE_NAME])
            table_exists = cursor.fetchone()[0]
            if not table_exists:
                create_table_query = f"""CREATE TABLE {TABLE_NAME}(
                                        {UNIQUE_ID} VARCHAR2(30))
                                    """
                cursor.execute(create_table_query)
                connection.commit()
                print(f"Table {TABLE_NAME} created successfully!")
            else:
                print(f"Table {TABLE_NAME} already exists.")


def insert_to_oracle(batch):
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(f"INSERT INTO {TABLE_NAME} ({UNIQUE_ID}) VALUES (:1)", [(i,) for i in batch])
            connection.commit()
    except Exception as e:
        print("Insert failed:", e)

def fetch_ids_for_slice(slice_id):
    url = f"{ES_HOST}/{INDEX_NAME}/_search?scroll=2m"
    query = {
        "size": BATCH_SIZE,
        "slice": {
            "id": slice_id,
            "max": SLICE_COUNT
        },
        "_source": False,  # Only fetch _id
        "query": {
            "match_all": {}
        }
    }

    res = requests.post(url, json=query, auth=ES_AUTH)
    res.raise_for_status()
    data = res.json()
    scroll_id = data['_scroll_id']
    hits = data['hits']['hits']

    total_count = 0

    # Progress bar setup for this slice
    pbar = tqdm(
        total=TOTAL_IDS_PER_SLICE,
        desc=f"Slice {slice_id}",
        bar_format=bar_format,
        dynamic_ncols=True,
    )

    while hits:
        ids = [hit['_id'] for hit in hits]
        insert_to_oracle(ids)
        total_count += len(ids)
        pbar.update(len(ids))

        scroll_url = f"{ES_HOST}/_search/scroll"
        scroll_query = {"scroll": "2m", "scroll_id": scroll_id}
        res = requests.post(scroll_url, json=scroll_query, auth=ES_AUTH)
        res.raise_for_status()
        data = res.json()
        scroll_id = data['_scroll_id']
        hits = data['hits']['hits']

    pbar.close()
    print(f"✅ Slice {slice_id} done: {total_count} records inserted. at time:", datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%d-%m-%Y %H:%M:%S'))
    
def main():
    start_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    print(f"Start time:",start_time.strftime('%Y-%m-%d %H:%M:%S'))
    create_db_table()
    print('TOTAL DATA COUNT ELK =',TOTAL_ID_COUNT)
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = []
        for i in range(SLICE_COUNT):
            futures.append(executor.submit(fetch_ids_for_slice, i))

        for future in futures:
            future.result()

    print("✅ Done inserting all IDs.")
    end_time = datetime.now(pytz.timezone('Asia/Kolkata'))
    print(f"End time:",end_time.strftime('%Y-%m-%d %H:%M:%S'))
    print(f"Time taken: {(end_time - start_time).total_seconds():.2f} seconds")

if __name__ == "__main__":
    main()
