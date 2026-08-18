import sys
import subprocess
import json


# -------------------------------
# LOAD CONFIG
# -------------------------------
def load_configuration(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)


# -------------------------------
# GET ACTIVE CLUSTERS
# -------------------------------
def get_active_emr_clusters(region, profile):
    try:
        output = subprocess.check_output([
            "aws", "emr", "list-clusters",
            "--cluster-states", "STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING",
            "--region", region,
            "--profile", profile,
            "--output", "json"
        ]).decode('utf-8')

        return json.loads(output).get("Clusters", [])
    except Exception as e:
        print(f"Error fetching clusters: {e}")
        return []


# -------------------------------
# FIND CLUSTERS BY NAME
# -------------------------------
def get_clusters_by_name(cluster_name, region, profile):
    clusters = get_active_emr_clusters(region, profile)

    matching = [
        c for c in clusters
        if c['Name'].strip().lower() == cluster_name.strip().lower()
    ]

    print(f"\nMatching clusters: {len(matching)}")

    for c in matching:
        print(f"{c['Id']} | {c['Status']['State']}")

    return matching


# -------------------------------
# DISABLE TERMINATION PROTECTION
# -------------------------------
def disable_termination_protection(cluster_id, region, profile):
    try:
        subprocess.check_call([
            "aws", "emr", "modify-cluster-attributes",
            "--cluster-id", cluster_id,
            "--no-termination-protected",
            "--region", region,
            "--profile", profile
        ])
        print(f"Disabled termination protection: {cluster_id}")

    except subprocess.CalledProcessError:
        print(f"⚠️ Could not disable protection for {cluster_id}")


# -------------------------------
# TERMINATE CLUSTERS
# -------------------------------
def terminate_clusters(cluster_ids, region, profile):
    try:
        subprocess.check_call([
            "aws", "emr", "terminate-clusters",
            "--cluster-ids"
        ] + cluster_ids + [
            "--region", region,
            "--profile", profile
        ])

        print(f"\nTermination started for: {cluster_ids}")

    except subprocess.CalledProcessError as e:
        print(f"Error terminating clusters: {e}")
        sys.exit(1)


# -------------------------------
# WAIT FOR TERMINATION
# -------------------------------
def wait_for_termination(cluster_id, region, profile):
    print(f"Waiting for {cluster_id} to terminate...")

    try:
        subprocess.check_call([
            "aws", "emr", "wait", "cluster-terminated",
            "--cluster-id", cluster_id,
            "--region", region,
            "--profile", profile
        ])
        print(f"{cluster_id} terminated ✅")

    except subprocess.CalledProcessError:
        print(f"⚠️ Error waiting for {cluster_id}")


# -------------------------------
# MAIN
# -------------------------------
def main():
    config_path = '/home/awsadmin/TransientQA/Customization/cluster-input.json'
    config = load_configuration(config_path)

    cluster_name = config['name']
    region = config['region']
    profile = config['profile']

    clusters = get_clusters_by_name(cluster_name, region, profile)

    if not clusters:
        print("\nNo active cluster found.")
        sys.exit(0)

    cluster_ids = [c['Id'] for c in clusters]

    # Step 1: Disable termination protection
    for cid in cluster_ids:
        disable_termination_protection(cid, region, profile)

    # Step 2: Terminate
    terminate_clusters(cluster_ids, region, profile)

    # Step 3: Wait for termination
    for cid in cluster_ids:
        wait_for_termination(cid, region, profile)

    print("\n🎉 All clusters terminated successfully!")


if __name__ == "__main__":
    main()
