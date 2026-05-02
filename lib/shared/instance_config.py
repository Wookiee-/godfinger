import os


def get_instance_storage_dir(serverData):
    instance_name = getattr(serverData, 'instance_name', None)
    if not instance_name and hasattr(serverData, 'GetServerVar'):
        instance_name = serverData.GetServerVar('instance_name')
    if not instance_name:
        instance_port = getattr(serverData, 'instance_port', None)
        if instance_port is None and hasattr(serverData, 'GetServerVar'):
            instance_port = serverData.GetServerVar('instance_port')
        instance_name = str(instance_port) if instance_port is not None else 'default'
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    instance_dir = os.path.join(base_dir, instance_name)
    os.makedirs(instance_dir, exist_ok=True)
    return instance_dir

def get_instance_config_path(plugin_name, serverData):
    """
    Returns the config path for a plugin for the current Godfinger instance.
    Falls back from configured instance name to instance port to a shared default.
    """
    instance_dir = get_instance_storage_dir(serverData)
    return os.path.join(instance_dir, f"{plugin_name}.json")


def get_instance_file_path(file_name, serverData):
    return os.path.join(get_instance_storage_dir(serverData), file_name)
