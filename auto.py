import time
import requests
import paramiko
import pika  # Ensure pika is installed for RabbitMQ interaction
from vastai import VastAI
import re

# Mailgun configuration
MAILGUN_DOMAIN = ""
SENDER_EMAIL = ""
MAILGUN_TOKEN = ""
RECIPIENT_EMAIL = "petereroshdy@gmail.com"
ssh_port=0
ssh_addr=0
# VastAI configuration
vast_sdk = VastAI(api_key='')

# Machine parameters
MACHINE_ID = 12245113  # Your specific machine ID
SSH_KEY_PATH = "/root/automation/id_rsa"

# RabbitMQ credentials and configuration
RABBITMQ_HOST = ''
RABBITMQ_PORT = 5672
RABBITMQ_USERNAME = ''
RABBITMQ_PASSWORD = ''
RABBITMQ_QUEUE = 'data'

local_file_path = "main.py"
remote_file_path = "/root/main.py"

# Function to send email via Mailgun
def send_mail(subject, body):
    return requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_TOKEN),
        data={"from": SENDER_EMAIL,
              "to": RECIPIENT_EMAIL,
              "subject": subject,
              "text": body})

# Step 1: Launch the instance
try:
    send_mail("Instance Launching", "Launching instance on vast.ai")
    print("Launching instance on vast.ai")
    instance = vast_sdk.launch_instance(num_gpus="2", gpu_name="RTX_4070S_Ti", image="pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime")
    match = re.search(r"'new_contract': (\d+)", instance)
    if match:
        instance_id = match.group(1)
        print(instance_id)
    
    # print(instance.show_ssh_host())
    ## convert instance_id to int
    instance_id = int(instance_id)
    details = vast_sdk.show_instance(id=instance_id)
    print(details)
    ssh_addr_match = re.search(r'\bssh\d+\.\S+\b', details)
    if ssh_addr_match:
        ssh_addr = ssh_addr_match.group(0)
        print(f"SSH Address: {ssh_addr}")
    else:
        print("SSH Address not found.")

    # Use regex to extract the SSH Port (finding exactly five digits)
    # Now we refine the search for the SSH Port by making sure it's after the SSH address
    ssh_port_match = re.search(rf'{ssh_addr}\s+(\d+)', details)
    if ssh_port_match:
        ssh_port = ssh_port_match.group(1)  # Capture the port number
        print(f"SSH Port: {ssh_port}")
    else:
        print("SSH Port not found.")



    # print(f"Instance {instance_id} launched with IP {public_ip}")
    # send_mail("Instance Launched", f"Instance {instance_id} launched with IP {public_ip}")
    time.sleep(90)  # Wait for instance to fully initialize
except Exception as e:
    send_mail("Instance Launch Failed", str(e))
    exit(1)

# Step 2: SSH into the instance, install dependencies, and run Python script
try:
    send_mail("Starting SSH Connection", f"Connecting to instance {instance_id} via SSH")
    ssh_username = 'root'  # Username for SSH (root)
    local_bind_port = 8080  # The local port to forward (8080)
    remote_bind_port = 8080  # The remote port to forward (8080)
    key_filename = SSH_KEY_PATH  # Path to your private SSH key

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting to {ssh_addr} on port {ssh_port} with username {ssh_username} and key file {key_filename}")

    # Connect to the remote server using the provided details
    ssh.connect(ssh_addr, port=ssh_port, username=ssh_username, key_filename=key_filename)

    # Install dependencies
    ssh.exec_command("sudo apt update")

    # Step 2: Upload the main.py file
    sftp = ssh.open_sftp()
    sftp.put(local_file_path, remote_file_path)
    sftp.close()


except Exception as e:
    send_mail("SSH or Script Execution Failed", str(e))
    #vast_sdk.destroy_instance(id=instance_id)
    exit(1)

# Step 3: Check if the RabbitMQ queue is empty
def is_rabbitmq_queue_empty():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
            )
        )
        channel = connection.channel()
        queue = channel.queue_declare(queue=RABBITMQ_QUEUE, passive=True)
        message_count = queue.method.message_count
        connection.close()
        return message_count == 0
    except Exception as e:
        send_mail("RabbitMQ Connection Failed", str(e))
        return False

# Step 4: Destroy the instance if the RabbitMQ queue is empty
# try:
#     if is_rabbitmq_queue_empty():
#         print("Queue is empty. Destroying instance")
#         send_mail("Destroying Instance", f"Queue is empty. Destroying instance {instance_id}")
#         vast_sdk.destroy_instance(id=instance_id)
#         send_mail("Instance Destroyed", f"Instance {instance_id} has been successfully destroyed.")
#     else:
#         send_mail("Instance Retained", f"Queue is not empty. Instance {instance_id} is retained.")
# except Exception as e:
#     send_mail("Instance Destruction Failed", str(e))
