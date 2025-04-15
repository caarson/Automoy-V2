import atexit
import ssl
import requests
from pyVim import connect
from pyVmomi import vim

class VMWareInterface:
    def __init__(self, host, user, password, port=443):
        """
        Initializes connection to VMware vSphere/ESXi.
        
        :param host: VMware host IP or hostname.
        :param user: Username for authentication.
        :param password: Password for authentication.
        :param port: Port number (default: 443).
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.si = None  # Service Instance

    def connect(self):
        """Establishes connection to the VMware ESXi/vCenter Server."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.verify_mode = ssl.CERT_NONE  # Ignore SSL warnings

        try:
            self.si = connect.SmartConnect(
                host=self.host, user=self.user, pwd=self.password, port=self.port, sslContext=context
            )
            atexit.register(connect.Disconnect, self.si)  # Ensure clean disconnect
            print("✅ Connected to VMware vSphere/ESXi!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def list_vms(self):
        """Retrieves a list of VMs on the ESXi/vCenter host."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return []

        content = self.si.RetrieveContent()
        container = content.rootFolder
        viewType = [vim.VirtualMachine]
        recursive = True
        containerView = content.viewManager.CreateContainerView(container, viewType, recursive)
        
        vms = containerView.view
        return [vm.name for vm in vms]

    def create_vm(self, vm_name, datastore_name, guest_os, memory_mb=1024, cpus=1):
        """
        Creates a VM with specified configurations.
        
        :param vm_name: Name of the virtual machine.
        :param datastore_name: Datastore to use.
        :param guest_os: Guest OS type.
        :param memory_mb: Memory in MB (default: 1024).
        :param cpus: Number of CPUs (default: 1).
        """
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        content = self.si.RetrieveContent()
        datacenter = content.rootFolder.childEntity[0]  # Assume single datacenter
        vm_folder = datacenter.vmFolder
        resource_pool = datacenter.hostFolder.childEntity[0].resourcePool
        datastore = [ds for ds in datacenter.datastoreFolder.childEntity if ds.name == datastore_name][0]

        vm_config = vim.vm.ConfigSpec(
            name=vm_name,
            memoryMB=memory_mb,
            numCPUs=cpus,
            guestId=guest_os,
            files=vim.vm.FileInfo(logDirectory=None, snapshotDirectory=None, suspendDirectory=None, vmPathName=f"[{datastore_name}]"),
        )

        task = vm_folder.CreateVM_Task(config=vm_config, pool=resource_pool)
        print(f"🚀 Creating VM `{vm_name}`... Task initiated.")
        return task

    def power_on_vm(self, vm_name):
        """Powers on a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        content = self.si.RetrieveContent()
        vm = self._get_vm_by_name(content, vm_name)

        if vm:
            task = vm.PowerOnVM_Task()
            print(f"🔌 Powering on `{vm_name}`... Task initiated.")
            return task
        else:
            print(f"⚠️ VM `{vm_name}` not found.")

    def power_off_vm(self, vm_name):
        """Powers off a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        content = self.si.RetrieveContent()
        vm = self._get_vm_by_name(content, vm_name)

        if vm:
            task = vm.PowerOffVM_Task()
            print(f"⛔ Powering off `{vm_name}`... Task initiated.")
            return task
        else:
            print(f"⚠️ VM `{vm_name}` not found.")

    def delete_vm(self, vm_name):
        """Deletes a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        content = self.si.RetrieveContent()
        vm = self._get_vm_by_name(content, vm_name)

        if vm:
            task = vm.Destroy_Task()
            print(f"🗑️ Deleting `{vm_name}`... Task initiated.")
            return task
        else:
            print(f"⚠️ VM `{vm_name}` not found.")

    def _get_vm_by_name(self, content, vm_name):
        """Helper function to find a VM by name."""
        container = content.rootFolder
        viewType = [vim.VirtualMachine]
        recursive = True
        containerView = content.viewManager.CreateContainerView(container, viewType, recursive)

        for vm in containerView.view:
            if vm.name == vm_name:
                return vm
        return None
    
    def is_vmware_installed(self):
        return False  # or True, depending on what you want for now

# Example Usage:
if __name__ == "__main__":
    vmware = VMWareInterface(host="your-vmware-host", user="your-username", password="your-password")
    
    if vmware.connect():
        print("Available VMs:", vmware.list_vms())
        vmware.create_vm(vm_name="Automoy-VM", datastore_name="datastore1", guest_os="otherGuest")
