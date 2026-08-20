from elasticsearch import Elasticsearch
import json
import requests
import pandas as pd
from datetime import datetime
import pytz


def check_mapping(prod_mappings_dict,dev_mappings_dict):
    if prod_mappings_dict == dev_mappings_dict:
        print("Mapping is same")
    else:
        print("Mapping is NOT same. please check.")
        if len(dev_mappings_dict) != len(prod_mappings_dict):
            long_dict, short_dict = (prod_mappings_dict, dev_mappings_dict) if len(prod_mappings_dict) > len(dev_mappings_dict) else (dev_mappings_dict,prod_mappings_dict)
            result_dict = {k: v for k, v in long_dict.items() if k not in short_dict}
            print(f"Extra key(s) are in {'PROD' if long_dict is prod_mappings_dict else 'DEV'}: {result_dict.keys()}")
        for key, val in prod_mappings_dict.items():
            if key in dev_mappings_dict:
                if val != dev_mappings_dict[key]:
                    print(f"Prod_mapping - {key} : {val}")
                    print(f"Dev_mapping - {key} : {dev_mappings_dict[key]}",end='\n\n')
            # else:
            #     print(f"{key} is not present in Dev")

        # for key, val in dev_mappings_dict.items():
        #     if key in prod_mappings_dict:
        #         if val != prod_mappings_dict[key]:
        #             print(f"Prod_mapping - {key} : {prod_mappings_dict[key]}")
        #             print(f"Dev_mapping - {key} : {val}")
        #     else:
        #         print(f"{key} is not present in Prod",end='\n')

def fetch_all_ids_dev(index_name,es_dev):
    # Use a scroll query to fetch all documents in batches
    scroll_time = "2m"  # Keep the scroll context open for 2 minutes
    batch_size = 1000  # Number of docs per batch

    # Initialize the scroll
    response = es_dev.search(index=index_name, 
                         body={"query": {"match_all": {}}}, 
                         scroll=scroll_time, 
                         size=batch_size)

    scroll_id = response["_scroll_id"]
    total_docs = response["hits"]["total"]["value"]

    print(f"Total documents to fetch: {total_docs}")

    # Collect all the _id values
    ids = [hit["_id"] for hit in response["hits"]["hits"]]

    # Loop through the rest of the data using the scroll ID
    while True:
        response = es_dev.scroll(scroll_id=scroll_id, scroll=scroll_time)
        
        # Break if no more data is found
        if not response["hits"]["hits"]:
            break

        # Append the _id values from this batch
        ids.extend([hit["_id"] for hit in response["hits"]["hits"]])

        # Update the scroll ID for the next batch
        scroll_id = response["_scroll_id"]

    return ids

def fetch_data_for_ids(index_name, id_list, elk_url):
    es_url = f"{elk_url}/{index_name}/_search"
    # Use a 'terms' query to filter by _id
    query = {
        "query": {
            "terms": {
                "_id": id_list
            }
        },
        "size": len(id_list)
    }

    response = requests.get(es_url, headers={"Content-Type": "application/json"}, data=json.dumps(query))
    dev_data_dict = response.json()
    # Extract documents from the response
    # print(dev_data_dict)
    docs = [hit["_source"] for hit in dev_data_dict["hits"]["hits"]]

    return docs

mismatch_list = []

def check_data(prod_data,dev_data,query_field,query_field_value):
    if prod_data != dev_data:
        # print("Data is Incorrect")
        mismatch_dict = {}
        if len(dev_data) != (prod_data):
            # long_dict, short_dict = (prod_data, dev_data) if len(prod_data) > len(dev_data) else (dev_data,prod_data)
            # result_dict = {k: v for k, v in long_dict.items() if k not in short_dict}
            # print(f"Extra key(s) are in {'PROD' if long_dict is prod_data else 'DEV'}: {result_dict}")
            mismatch_dict[f'{query_field}'] = query_field_value
            for key, val in prod_data.items():
                if key in dev_data:
                    # print("Matched Values:")
                    # print(f"Dev_data - {key} : {dev_data[key]} {type(dev_data[key])}")
                    # print(f"Prod_data - {key} : {val} {type(val)}")
                    if val != dev_data[key]:
                    # print("Mismatch items:")
                    # print(f"Dev_data - {key} : {dev_data[key]} {type(dev_data[key])}")
                    # print(f"Prod_data - {key} : {val} {type(val)}")
                        mismatch_dict[f'{key}_dev'] = dev_data[key]
                        mismatch_dict[f'{key}_prod'] = val
                # else:
                #     print(f"key : {key} is not present in Dev")
            mismatch_list.append(mismatch_dict)

def batch_fetch_data(index_name, id_list,elk_url, batch_size=1000):
    all_data = []
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        # print('len(batch) - ',len(batch))
        data = fetch_data_for_ids(index_name, batch, elk_url)
        # print('len(data) - ',len(data))
        all_data.extend(data)
    return all_data


if __name__ == '__main__':
    index_name_list = ['flat_accr_loyalaty']
    for index in index_name_list:
        index_name = index

        print(f"---- Table Name : {index_name} ----")
        start_time = datetime.now(pytz.timezone('Asia/Kolkata'))
        print(f"Start time:",start_time.strftime('%Y-%m-%d %H:%M:%S'))

        prod_index_name = f"{index_name}"
        dev_index_name = f"{index_name}_python_test"

        prod_elk_url = 'http://11.12.14.14:9200'
        dev_elk_url = 'http://11.22.33.44:9200'

        # Make the GET request to retrieve the mappings
        prod_response = requests.get(f"{prod_elk_url}/{prod_index_name}/_mapping")
        dev_response = requests.get(f"{dev_elk_url}/{dev_index_name}/_mapping")

        # Convert the JSON response to a Python dictionary
        prod_mappings = prod_response.json()
        dev_mappings = dev_response.json()

        prod_mappings_dict = prod_mappings[prod_index_name]['mappings']['properties']
        dev_mappings_dict = dev_mappings[dev_index_name]['mappings']['properties']

        check_mapping(prod_mappings_dict,dev_mappings_dict)

        es_dev = Elasticsearch(dev_elk_url)
        dev_ids = fetch_all_ids_dev(dev_index_name,es_dev)

        print('dev_ids - ',len(dev_ids))

        dev_data_list = batch_fetch_data(dev_index_name, dev_ids,dev_elk_url)
        prod_data_list = batch_fetch_data(index_name, dev_ids,prod_elk_url)
        # dev_data_list = fetch_data_for_ids(dev_index_name, dev_ids, dev_es_url)
        # prod_data_list = fetch_data_for_ids(index_name, dev_ids, prod_es_url)

        print('dev_data_list - ',len(dev_data_list))
        print('prod_data_list - ',len(prod_data_list))
        
        if len(prod_data_list) == 0:
            print('prod_data_list is 0 so exit')
            continue
        query_field = [key for key,val in dev_data_list[0].items() if val == dev_ids[0]]

        for wid in dev_ids:
            prod_data = next(filter(lambda x: x.get(query_field[0]) == wid, prod_data_list), False)
            dev_data = next(filter(lambda x: x.get(query_field[0]) == wid, dev_data_list), False)
            if (dev_data != False) and (prod_data != False):
                check_data(prod_data,dev_data,query_field[0],wid)

        if len(mismatch_list) != 0:
            df = pd.DataFrame(mismatch_list)
            print(df.shape)
            df.to_csv(f'{index_name}_elk_data_validation.csv', index=False)
            print("CSV file created successfully!")
        else:
            print("Data is correct hence No CSV generated!")

        end_time = datetime.now(pytz.timezone('Asia/Kolkata'))
        print(f"End time:",end_time.strftime('%Y-%m-%d %H:%M:%S'))
        print(f"Time taken: {(end_time - start_time).total_seconds():.2f} seconds")
