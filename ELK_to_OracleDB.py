import requests
import json
import oracledb
import os
from dotenv import load_dotenv

load_dotenv()

db_credential = {
    "host_address" : os.environ.get('dealer_olap_prod_host_address'),
    "port" : os.environ.get('dealer_olap_prod_port'),
    "service_name" : os.environ.get('dealer_olap_prod_service_name'),
    "user_name" : os.environ.get('dealer_olap_prod_username'),
    "password" : os.environ.get('dealer_olap_prod_password')
}

# Create a connection pool
pool = oracledb.create_pool(
    user=db_credential['user_name'],
    password=db_credential['password'],
    dsn=f"{db_credential['host_address']}:{db_credential['port']}/{db_credential['service_name']}"
)

# ELK server details
SOURCE_ELK = "http://11.22.33.44:9200"
INDEX_NAME = "dealer_wsr"  # Change this to your index name
table_name = "dealer_wsr_index"  # Change this if needed

# Optional authentication (if required)
AUTH1 = ("elastic", "elastic")  # Change if authentication is needed, otherwise set to None
AUTH2 = ("elastic", "elastic")  # Change if authentication is needed, otherwise set to None

HEADERS = {"Content-Type": "application/json"}

def check_index_exists(elk_url, index_name):
    """Check if the index exists on the ELK server"""
    response = requests.head(f"{elk_url}/{index_name}", auth=AUTH1)
    return response.status_code == 200

def get_index_mapping():
    """Get index mapping and settings from the source ELK server"""
    mapping_url = f"{SOURCE_ELK}/{INDEX_NAME}"
    response = requests.get(mapping_url, headers=HEADERS, auth=AUTH1)
    if response.status_code == 200:
        return response.json()
    else:
        print("Error fetching index mapping:", response.text)
        return None

def fetch_index_data():
    """Fetch all documents from the source index using the scroll API"""
    search_url = f"{SOURCE_ELK}/{INDEX_NAME}/_search?scroll=2m"
    query = {"query": {"match_all": {}}, "size": 10000}

    response = requests.get(search_url, headers=HEADERS, auth=AUTH1, json=query)
    if response.status_code != 200:
        print("Error fetching index data:", response.text)
        return None, None

    data = response.json()
    return data.get("_scroll_id"), data["hits"]["hits"]

def scroll_data(scroll_id):
    """Fetch next batch of data using the scroll ID"""
    scroll_url = f"{SOURCE_ELK}/_search/scroll"
    payload = {"scroll": "2m", "scroll_id": scroll_id}

    response = requests.get(scroll_url, headers=HEADERS, auth=AUTH1, json=payload)
    if response.status_code != 200:
        print("Error scrolling data:", response.text)
        return None, None

    data = response.json()
    return data.get("_scroll_id"), data["hits"]["hits"]

def create_table(table_name,columns_datatype):
    data_type_map = {'text':'VARCHAR2(50 BYTE)','float':'FLOAT','long':'NUMBER','date':'DATE'}
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM user_tables WHERE table_name = UPPER(:1)", [table_name])
            table_exists = cursor.fetchone()[0]
            if not table_exists:
                query_start = f'CREATE TABLE {table_name.upper()}(\n'
                body = ''
                for col,data_type in columns_datatype.items():
                    body += f'"{col.upper()}" {data_type_map.get(data_type, "VARCHAR2(50 BYTE)")},\n'
                body = body.rstrip(',\n') + ')'
                create_table_query = query_start+body
                cursor.execute(create_table_query)
                connection.commit()
                print(f"Table {table_name} created successfully!")
            else:
                print(f"Table {table_name} already exists.")


def bulk_insert_data(documents,columns):
    """Send data to the target ELK server using the bulk API"""
    data_list = []
    for i in documents:
        values=[]
        for col in columns:
            values.append(i['_source'].get(col,None))
        data_list.append(tuple(values))

    binds = ''
    for i in range(1,len(columns)+1):
        binds += f":{i}, "
    binds = binds.rstrip(', ')
    columns = [col.upper() for col in columns]
    columns = "(" + ", ".join(columns) + ")"
    query = f"""INSERT INTO {table_name.upper()} {columns} VALUES ({binds})"""
    print(data_list)
    print(query)
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            print('i am here...')
            cursor.executemany(query, data_list)
            connection.commit()

def copy_index_data():
    """Main function to copy index data from source to target ELK"""
    
    # Check if the source index exists
    if not check_index_exists(SOURCE_ELK, INDEX_NAME):
        print(f"Source index '{INDEX_NAME}' does not exist.")
        return

    # Get and create index mapping
    mapping_data = get_index_mapping()
    if not mapping_data:
        return
    
    columns_datatype = {}
    for key,val in mapping_data[INDEX_NAME]['mappings']['properties'].items():
        columns_datatype[key] = val['type']

    
    # table_name = 'dealer_wsr'
    create_table(table_name,columns_datatype)

    # Fetch first batch of data
    scroll_id, docs = fetch_index_data()
    if not scroll_id:
        print("No data found in index.")
        return

    total_copied = 0
    while docs:
        bulk_insert_data(docs,list(columns_datatype.keys()))
        total_copied += len(docs)
        print(f"Copied {total_copied} documents...")

        # Fetch next batch
        scroll_id, docs = scroll_data(scroll_id)

    print(f"Data transfer complete. Total {total_copied} documents copied.")

if __name__ == "__main__":
    copy_index_data()
