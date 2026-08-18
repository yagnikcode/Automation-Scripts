import subprocess
import json
import traceback

def list_docker_network_subnets():
    try:
        # Run the 'docker network ls' command to get the list of network IDs
        networks_output = subprocess.check_output(['docker', 'network', 'ls', '--format', '{{.ID}} {{.Name}}'], universal_newlines=True)
        networks = networks_output.strip().splitlines()
        for network in networks:
            network_id, network_name = network.split()

            # Run 'docker network inspect' to get details about each network
            inspect_output = subprocess.check_output(['docker', 'network', 'inspect', network_id], universal_newlines=True)
            network_details = json.loads(inspect_output)

            subnet_info = []

            if 'IPAM' in network_details[0] and 'Config' in network_details[0]['IPAM']:
                ipam_config = network_details[0]['IPAM']['Config']
#                print(ipam_config)
                if ipam_config is not None:
                  for config in ipam_config:
                      subnet = config.get('Subnet')
                      if subnet:
                          subnet_info.append(subnet)

            print(f"Subnets: {', '.join(subnet_info) if subnet_info else 'None'} Network: {network_name}")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running a Docker command: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    list_docker_network_subnets()

