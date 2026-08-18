import sys, subprocess

N=sys.argv[1]
name=sys.argv[2]
profile=sys.argv[3]

cmd = [
    "aws", "emr", "list-clusters",
    "--active",
    "--region", "ap-south-1",
    "--profile", profile,
    "--query", f"Clusters[?contains(Name, '{name}')].Id | [0]",
    "--output", "text"
]

cluster_id = subprocess.check_output(cmd).decode("utf-8").strip()

if not cluster_id:
    print("ERROR: No cluster found with name:", name)
    sys.exit(1)

cmd = [
    "aws", "emr", "list-instances",
    "--cluster-id", cluster_id,
    "--instance-group-types", "TASK",
    "--region", "ap-south-1",
    "--profile", profile,
    "--query", "Instances[].InstanceGroupId",
    "--output", "text"
]

instance_group_id = subprocess.check_output(cmd).decode("utf-8").strip()

if not instance_group_id:
    print("ERROR: No TASK instance group found")
    sys.exit(1)

subprocess.run([
    "aws", "emr", "modify-instance-groups",
    "--instance-groups",
    f"InstanceGroupId={instance_group_id},InstanceCount={N}",
    "--region", "ap-south-1",
    "--profile", profile
])

print(f"Requested {N} nodes are being provisioned...")
