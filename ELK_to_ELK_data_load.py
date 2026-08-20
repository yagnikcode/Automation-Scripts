import requests
import json

# ELK server details
SOURCE_ELK = "http://11.12.13.14:9200"
TARGET_ELK = "http://11.22.33.44:9200"
INDEX_NAME = "asset_data"  # Change this to your index name
NEW_INDEX_NAME = "asset_data"  # Change this if needed

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

def create_target_index(mapping_data):
    """Create the target index on the target ELK server with the same settings/mappings"""
    index_settings = mapping_data.get(INDEX_NAME, {}).get("settings", {}).get("index", {})

    # Remove unwanted system-generated settings
    forbidden_keys = ["provided_name", "creation_date", "uuid", "version"]
    clean_settings = {k: v for k, v in index_settings.items() if k not in forbidden_keys}

    mappings = mapping_data.get(INDEX_NAME, {}).get("mappings", {})

    create_url = f"{TARGET_ELK}/{NEW_INDEX_NAME}"
    payload = json.dumps({"settings": {"index": clean_settings}, "mappings": mappings})

    response = requests.put(create_url, headers=HEADERS, auth=AUTH2, data=payload)
    if response.status_code in [200, 201]:
        print(f"Index '{NEW_INDEX_NAME}' created successfully.")
    else:
        print("Error creating index:", response.text)


def fetch_index_data():
    """Fetch all documents from the source index using the scroll API"""
    search_url = f"{SOURCE_ELK}/{INDEX_NAME}/_search?scroll=2m"
    # query = {"query": {"match_all": {}}, "size": 10}
    query = {
        "size": 10000,
    "query": {
        "range": {
        "FIRST_SALE_DT_DATE": {
            "gte": "2025-06-01",
            "lte": "2025-06-08"
        }
        }
    }
    }

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

def bulk_insert_data(documents):
    """Send data to the target ELK server using the bulk API"""
    bulk_url = f"{TARGET_ELK}/_bulk"
    bulk_data = ""

    for doc in documents:
        action = {"index": {"_index": NEW_INDEX_NAME,"_id" : doc["_source"]['SRC_ROW_WID']}}
        # action = {"index": {"_index": NEW_INDEX_NAME}}
        bulk_data += json.dumps(action) + "\n" + json.dumps(doc["_source"]) + "\n"

    response = requests.post(bulk_url, headers=HEADERS, auth=AUTH2, data=bulk_data)
    if response.status_code != 200:
        print("Error inserting data:", response.text)

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

    # print(mapping_data)
    if not check_index_exists(TARGET_ELK, NEW_INDEX_NAME):
        create_target_index(mapping_data)

    # Fetch first batch of data
    scroll_id, docs = fetch_index_data()
    if not scroll_id:
        print("No data found in index.")
        return

    total_copied = 0
    while docs:
        bulk_insert_data(docs)
        total_copied += len(docs)
        print(f"Copied {total_copied} documents...")

        # Fetch next batch
        scroll_id, docs = scroll_data(scroll_id)

    print(f"Data transfer complete. Total {total_copied} documents copied.")

if __name__ == "__main__":
    copy_index_data()
