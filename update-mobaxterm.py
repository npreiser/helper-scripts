import configparser
import json
import boto3
import time
import subprocess
import sys

ini_path = r"c:\Users\npreiser\AppData\Roaming\MobaXterm\MobaXterm.ini"

pem_path = r"_CurrentDrive_:\A_LocalGit\MIPS\AWS_STUFF\nickp-mpe-kp-6-7-2024.pem"


def is_mobaxterm_running():
    """
    Checks if MobaXterm is currently running.
    Returns True if running, False otherwise.
    """
    if sys.platform.startswith("win"):
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq MobaXterm.exe"],
                capture_output=True,
                text=True,
            )
            return "MobaXterm.exe" in result.stdout
        except Exception as e:
            print(f"Error checking MobaXterm status: {e}")
    return False


def close_mobaxterm():
    """
    Closes the MobaXterm application if it is running.
    """
    if sys.platform.startswith("win"):
        # Windows: use taskkill
        try:
            subprocess.run(
                ["taskkill", "/IM", "MobaXterm.exe", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("Closed MobaXterm.")
        except Exception as e:
            print(f"Error closing MobaXterm: {e}")
    else:
        # Other platforms: try pkill
        try:
            subprocess.run(
                ["pkill", "-f", "MobaXterm"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("Closed MobaXterm.")
        except Exception as e:
            print(f"Error closing MobaXterm: {e}")


def reopen_mobaxterm():
    """
    Reopens MobaXterm.
    """
    mobaxterm_path = r"C:\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe"

    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["cmd", "/c", "start", "", mobaxterm_path],
                check=False,
                shell=False,  # Don't use shell=True for security
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("Reopened MobaXterm.")
            # Give MobaXterm some time to initialize
            time.sleep(2)
            return True
        except Exception as e:
            print(f"Error reopening MobaXterm: {e}")
            return False
    return False

def get_channel_info():
    print("Fetching channel information from DynamoDB...")
    dbResource = boto3.resource("dynamodb", region_name="us-west-2")
    table = dbResource.Table("global-channel-list")
    # endpoint_table = dbResource.Table("global-endpoint-list")

    # Get all channels
    channels = table.scan()["Items"]
    result = {}

    for channel in channels:
        channel_name = channel["channel"]
        regions = json.loads(channel.get("regions", "[]"))
        channel_info = {"regions": {}}
        for region in regions:
            # Get EC2 instances for this channel in this region
            print(
                f"Fetching instances for channel '{channel_name}' in region '{region}'"
            )
            ec2_client = boto3.client("ec2", region_name=region)
            instances = []
            try:
                reservations = ec2_client.describe_instances(
                    Filters=[
                        {"Name": "tag:channel", "Values": [channel_name]},
                        {
                            "Name": "instance-state-name",
                            "Values": ["running", "pending", "stopping", "stopped"],
                        },
                    ]
                )["Reservations"]
                for res in reservations:
                    for inst in res["Instances"]:
                        name = ""
                        for tag in inst.get("Tags", []):
                            if tag["Key"] == "Name":
                                name = tag["Value"]
                        instances.append(
                            {
                                #   "instance_id": inst["InstanceId"],
                                "name": name,
                                #  "state": inst["State"]["Name"],
                                "public_dns": inst.get("PublicDnsName", ""),
                                #   "private_ip": inst.get("PrivateIpAddress", ""),
                            }
                        )
            except Exception as e:
                instances = [{"error": str(e)}]
            channel_info["regions"][region] = instances
        result[channel_name] = channel_info

    print("Channel information fetched successfully.")
    return result


def update_mobaxterm_hosts():

    channelinfo = get_channel_info()

    section_name = None

    # First, find the section with SubRep=MIPS_CLOUD
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.optionxform = str  # preserve case
    config.read(ini_path, encoding="utf-8")

    for section in config.sections():
        if (
            config.has_option(section, "SubRep")
            and config[section]["SubRep"] == "MIPS_CLOUD"
        ):
            section_name = section
            break

    if section_name:
        # Keep only SubRep and ImgNum
        items_to_keep = {"SubRep", "ImgNum"}
        keys_to_remove = [k for k in config[section_name] if k not in items_to_keep]
        print(
            f"Found section [{section_name}] with SubRep=MIPS_CLOUD. Removing other keys."
        )
        for k in keys_to_remove:
            config.remove_option(section_name, k)

        # suffix = "%22%ubuntu%%-1%-1%%%%%0%0%0%_CurrentDrive_:\\A_LocalGit\\MIPS\\AWS_STUFF\\nickp-mpe-kp-6-7-2024.pem%%-1%0%0%0%%1080%%0%0%1%%0%%%%0%-1%-1%0#MobaFont%10%0%0%-1%15%236,236,236%30,30,30%180,180,192%0%-1%0%%xterm%-1%0%_Std_Colors_0_%80%24%0%1%-1%<none>%%0%0%-1%0%#0# #-1"
        suffix = (
            "%22%ubuntu%%-1%-1%%%%%0%0%0%"
            + pem_path
            + "%%-1%0%0%0%%1080%%0%0%1%%0%%%%0%-1%-1%0#MobaFont%10%0%0%-1%15%236,236,236%30,30,30%180,180,192%0%-1%0%%xterm%-1%0%_Std_Colors_0_%80%24%0%1%-1%<none>%%0%0%-1%0%#0# #-1"
        )

        prefix = "#109#0%"
        host_updates = {
            "boogersession333": "my.custom.dns.com",
            # Add more as needed
        }

        print("Updating section with channel information...")
        for channel, info in channelinfo.items():
            for region, instances in info["regions"].items():
                channel_region = f"{channel}_{region}"
                for instance in instances:
                    for idx, instance in enumerate(instances, 1):
                        channel_region_instance = f"{channel_region}_{idx}"
                        public_dns = instance.get("public_dns", "")
                        # You can use channel_region_instance and public_dns as needed here
                        config.set(
                            section_name,
                            channel_region_instance,
                            f"{prefix}{public_dns}{suffix}",
                        )

        # for key, value in host_updates.items():
        #    config.set(section_name, key, f"{prefix}{value}{suffix}")

        # Write back to file
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)

        print(f"Cleared section [{section_name}], kept only SubRep and ImgNum.")
    else:
        print("Section with SubRep=MIPS_CLOUD not found.")



if __name__ == "__main__":
    
    # Check if MobaXterm is running before making changes
    was_running = is_mobaxterm_running()
    if was_running:
        print("MobaXterm is currently running. Will reopen after updates.")

    # Close MobaXterm if it's running
    close_mobaxterm()

    # Update hosts file
    update_mobaxterm_hosts()

    # Reopen MobaXterm if it was running before
    if was_running:
        reopen_mobaxterm()
    else:
        print("MobaXterm was not running before, not reopening.")
