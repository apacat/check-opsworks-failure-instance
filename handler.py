import boto3
import os
import pychatwork as ch
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('opsworks',
                      region_name=os.environ['opsworks_api_resion'])
chatwork_client = ch.ChatworkClient(os.environ['chatwork_api_token'])

# chatwork settings
chatwork_roomid = int(os.environ['chatwork_roomid'])


def lambda_handler(event, context):
    """ Main function """
    stack_ids = os.environ['stackids'].split(',')
    stacks = get_stack_summary(stack_ids)
    if not stacks:
        logger.info('no failure instance')
        return

    failure_stacks = {}
    for stack in stacks:
        stack_name = stack['StackSummary']['Name']
        stack_id = stack['StackSummary']['StackId']
        failure_stacks[stack_name] = get_instance_info(stack_name, stack_id)

    msg = make_msg(failure_stacks)
    postdata = os.environ['temp_msg'].format('\n'.join(msg))

    try:
        chatwork_client.post_messages(
            room_id=chatwork_roomid, message=postdata)
    except Exception as e:
        logger.error('post error')
        raise(str(e))

    return "end"


def get_stack_summary(stack_ids: list):
    """
    Get stack with failure instance

    Returns:
        list
    """
    stack_summary = []
    for stack_id in stack_ids:
        stack_summary.append(
            client.describe_stack_summary(StackId=stack_id))

    stacks_with_failure_instance = []
    for stack in stack_summary:
        instancescount = stack['StackSummary']['InstancesCount']
        setupfailed = instancescount.get('SetupFailed')
        startupfailed = instancescount.get('StartFailed')
        if setupfailed or startupfailed:
            stacks_with_failure_instance.append(stack)

    return stacks_with_failure_instance


def get_instance_info(stack_name: str, stack_id: str):
    """
    Get failure instance info

    Returns:
        list
    """
    instance_result = {}
    instances = []
    instances.append(
        client.describe_instances(StackId=stack_id))

    failure_instances = [instance for instance in instances[0]['Instances'] if instance['Status'] == 'setup_failed' or instance['Status'] == 'running_failed']
    for instance in failure_instances:
        instance_result[instance['Hostname']] = instance['Status']

    return instance_result


def make_msg(msg_data: dict):
    """
    Make ChatWork Post msg

    Returns:
        list
    """
    chatwork_msg_temp = '- stackname: {0}\n\t- hostname: {1}\n\t\t- status: {2}'
    msg = []
    for stack_name, instances in msg_data.items():
        for hostname, status in instances.items():
            msg.append(chatwork_msg_temp.format(stack_name, hostname, status))

    return msg
