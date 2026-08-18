import sys
import subprocess
import json
import time

N = int(sys.argv[1])   # target nodes (e.g. 15)
name = str(sys.argv[2])
profile = str(sys.argv[3])

region = "ap-south-1"
timeout = 1800   # 30 minutes
interval = 30    # check every 30 seconds

start_time = time.time()

# Get cluster ID
cmd = f"aws emr list-clusters --active --region {region} --profile {profile}"
clusters = subprocess.check_output(cmd, shell=True)
clusters_json = json.loads(clusters)

cluster_id = None
for cluster in clusters_json["Clusters"]:
    if cluster["Name"] == name:
        cluster_id = cluster["Id"]
        break

if not cluster_id:
    print("Cluster not found")
    sys.exit(1)

print("Cluster ID:", cluster_id)

# Loop until node count reached or timeout
while True:

    cmd_nodes = f"""
        aws emr list-instances \
        --cluster-id {cluster_id} \
        --instance-states RUNNING \
        --region {region} \
        --profile {profile} \
        --query "length(Instances)"
        """

    node_count = subprocess.check_output(cmd_nodes, shell=True).decode().strip()
    node_count = int(node_count)

    print("Active Nodes:", node_count)

    if node_count >= N:
        print(f"Target reached: {node_count} nodes available")
        break

    elapsed = time.time() - start_time
    if elapsed > timeout:
        print("ERROR: Node count did not reach target within 30 minutes")
        sys.exit(1)

    print("Waiting for nodes to scale...")
    time.sleep(interval)
  
