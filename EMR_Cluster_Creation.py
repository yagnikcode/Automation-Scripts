'''
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
    Start --> Load configuration (load_configuration) --> Get active EMR clusters (get_active_emr_clusters) --> Check if cluster with same name exists
    |                                                                            |-- Yes --> Send the error mail and exit
    |                                                                            |-- No --> Continue
    v
    Create EMR cluster (create_emr_cluster) --> Get new cluster ID (get_cluster_id_by_name) --> Get master instance ID (get_master_instance_id) --> Attach network interface (attach_network_interface)
    |                                                                            |-- Success -->  success mail
    |                                                                            |-- Failure -->  failure mail
    v
    End
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
'''
#-- ==============================================================================================================================================================

import sys
import os
import subprocess
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(subject, message, mail_list):
    """
    Sends an email notification.

    Parameters:
    - subject: The subject of the email.
    - message: The message content to be sent.
    - mail_list: List of email addresses to send the message to.
    """
    msg = MIMEMultipart()
    body_part = MIMEText(message, 'plain')
    msg['Subject'] = subject
    msg['From'] = os.getenv("SERVER_MAIL_ID")
    msg['To'] = ', '.join(mail_list)
    msg.attach(body_part)
    smtpObj = smtplib.SMTP(os.getenv("SMTP_SERVER_IP"))
    smtpObj.sendmail(msg['From'], mail_list, msg.as_string())
    smtpObj.quit()

def load_configuration(file_path):
    """
    Loads the configuration from a Cluster Input JSON file.

    Parameters:
    - file_path: The path to the JSON file.

    Returns:
    - A dictionary containing the configuration data.
    """
    with open(file_path, 'r') as file:
        return json.load(file)

def get_active_emr_clusters(region, profile):
    """
    Retrieves the list of active EMR clusters.

    Parameters:
    - region: The AWS region.
    - profile: The AWS CLI profile to use.

    Returns:
    - A list of active EMR cluster names.
    """
    try:
        output = subprocess.check_output([
            "aws", "emr", "list-clusters",
            "--cluster-states", "STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING",
            "--region", region,
            "--profile", profile,
            "--output", "json"
        ]).decode('utf-8')
        clusters = json.loads(output)
        return clusters.get("Clusters", [])
    except Exception as e:
        print(f"Error fetching clusters: {e}")
        return []


# -------------------------------
# CHECK EXISTING CLUSTER
# -------------------------------
def check_existing_cluster(config):
    active_clusters = get_active_emr_clusters(config['region'], config['profile'])
    normalized_name = config['name'].strip().lower()
    matching_clusters = [
        c for c in active_clusters
        if c['Name'].strip().lower() == normalized_name
    ]
    print(f"\nTotal Active Clusters: {len(active_clusters)}")
    print(f"Matching Clusters: {len(matching_clusters)}")
    for c in matching_clusters:
        print(f"Cluster: {c['Id']} | State: {c['Status']['State']}")
    # -------------------------
    # BLOCK if RUNNING
    # -------------------------
    running_clusters = [
        c for c in matching_clusters
        if c['Status']['State'] in ["STARTING", "BOOTSTRAPPING", "RUNNING"]
    ]
    if running_clusters:
        print("\n❌ Cluster already running:")
        for c in running_clusters:
            print(f"{c['Id']} ({c['Status']['State']})")
        return None, "BLOCK"
    # -------------------------
    # REUSE if WAITING
    # -------------------------
    waiting_clusters = [
        c for c in matching_clusters
        if c['Status']['State'] == "WAITING"
    ]
    if waiting_clusters:
        # Sort latest first
        waiting_clusters.sort(
            key=lambda x: x['Status']['Timeline']['CreationDateTime'],
            reverse=True
        )
        cluster_id = waiting_clusters[0]['Id']
        print(f"\n♻️ Reusing cluster: {cluster_id}")
        # Optional: clean old duplicates
        if len(waiting_clusters) > 1:
            print("\nCleaning old clusters...")
            for c in waiting_clusters[1:]:
                subprocess.call([
                    "aws", "emr", "terminate-clusters",
                    "--cluster-ids", c['Id'],
                    "--region", config['region'],
                    "--profile", config['profile']
                ])
        return cluster_id, "REUSE"
    # -------------------------
    # CREATE NEW
    # -------------------------
    print("\n✅ No cluster found. Creating new.")
    return None, "CREATE"

def create_emr_cluster(config):
    """
    Creates an EMR cluster using the provided configuration.

    Parameters:
    - config: A dictionary containing the configuration for the EMR cluster.
    """
    print("\nCreating EMR cluster...")
    app_args = config['applications'].split()
    tag_args = config['tags'].split()
    command = [
        "aws", "emr", "create-cluster",
        "--applications"] + app_args + [
        "--tags"] + tag_args + [
        "--ec2-attributes", json.dumps(config['ec2-attributes']),
        "--release-label", config['release-label'],
        "--log-uri", config['log-uri'],
        "--instance-groups", json.dumps(config['instance-groups']),
        "--auto-scaling-role", config['auto-scaling-role'],
        "--bootstrap-actions", json.dumps(config['bootstrap-actions']),
        "--ebs-root-volume-size", str(config['ebs-root-volume-size']),
        "--service-role", config['service-role'],
        "--enable-debugging",
        "--name", config['name'],
        "--scale-down-behavior", config['scale-down-behavior'],
        "--region", config['region'],
        "--profile", config['profile'],
        "--output", "json"
    ]
    output = subprocess.check_output(command).decode('utf-8')
    response = json.loads(output)
    cluster_id = response.get("ClusterId")
    if not cluster_id:
        raise Exception("ClusterId not returned")
    print(f"Cluster created: {cluster_id}")
    return cluster_id

# -------------------------------
# WAIT FOR CLUSTER RUNNING
# -------------------------------
def wait_for_cluster(cluster_id, region, profile):
    print(f"\nWaiting for cluster {cluster_id} to be RUNNING...")
    subprocess.check_call([
        "aws", "emr", "wait", "cluster-running",
        "--cluster-id", cluster_id,
        "--region", region,
        "--profile", profile
    ])
    print("Cluster is RUNNING ✅")


def get_master_instance_id(cluster_id, region, profile):
    """
    Retrieves the master instance ID of an EMR cluster.

    Parameters:
    - cluster_id: The ID of the EMR cluster.
    - region: The AWS region.
    - profile: The AWS CLI profile to use.

    Returns:
    - The master instance ID of the EMR cluster.
    """
    print("\nFetching master instance...")
    output = subprocess.check_output([
        "aws", "emr", "list-instances",
        "--cluster-id", cluster_id,
        "--instance-group-types", "MASTER",
        "--region", region,
        "--profile", profile,
        "--output", "json"
    ]).decode('utf-8')
    instances = json.loads(output)
    instance_id = instances['Instances'][0]['Ec2InstanceId']
    print(f"Master Instance: {instance_id}")
    return instance_id


# -------------------------------
# ATTACH ENI (OPTIONAL)
# -------------------------------
def attach_network_interface(nw_id, instance_id, region, profile):
    """
    Attaches a network interface to an EC2 instance.

    Parameters:
    - cluster_name: EMR cluster name
    - nw_id: The network interface ID.
    - master_instance_id: The EC2 instance ID to attach the network interface to.
    - region: The AWS region.
    - profile: The AWS CLI profile to use.
    - mail_list: List of email addresses for sending notifications.
    - retries: Number of retry attempts.
    - delay: Delay between retries in seconds.

    Returns:
    - True if the network interface was successfully attached, False otherwise.
    """
    print("\nAttaching network interface...")
    try:
        subprocess.check_call([
            "aws", "ec2", "attach-network-interface",
            "--network-interface-id", nw_id,
            "--instance-id", instance_id,
            "--device-index", "1",
            "--region", region,
            "--profile", profile
        ])
        print("ENI attached successfully ✅")
    except subprocess.CalledProcessError:
        print("⚠️ Failed to attach ENI (continuing...)")


# -------------------------------
# MAIN
# -------------------------------
def main():
    # Load configuration from JSON file
    config_path = '/home/awsadmin/TransientQA/Customization/cluster-input.json'
    config = load_configuration(config_path)

    # Step 1: Check existing cluster
    cluster_id, action = check_existing_cluster(config)

    # Step 2: Decide flow
    if action == "BLOCK":
        sys.exit(1)
    elif action == "CREATE":
        cluster_id = create_emr_cluster(config)
    elif action == "REUSE":
        print("Using existing cluster...")

    # Step 3: Wait until ready
    wait_for_cluster(cluster_id, config['region'], config['profile'])

    # Step 4: Get master instance
    master_instance_id = get_master_instance_id(
        cluster_id,
        config['region'],
        config['profile']
    )

    # Step 5: Attach ENI (optional)
    if config.get("nw_id"):
        attach_network_interface(
            config['nw_id'],
            master_instance_id,
            config['region'],
            config['profile']
        )

    print("\n🎉 EMR Cluster Ready for Jobs!")


if __name__ == "__main__":
    main()
