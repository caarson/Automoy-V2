import atexit
import ssl
from pyVim import connect as vim_connect
from pyVmomi import vim

class VMWareInterface:
    def __init__(self, host: str, user: str, password: str, port: int = 443):
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

    def connect(self) -> bool:
        """Establishes connection to the VMware ESXi/vCenter Server."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.verify_mode = ssl.CERT_NONE  # Ignore SSL warnings

        try:
            self.si = vim_connect.SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context,
            )
            atexit.register(vim_connect.Disconnect, self.si)
            print("✅ Connected to VMware vSphere/ESXi!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.si = None
            return False

    def disconnect(self) -> None:
        """Disconnects cleanly from the VMware server."""
        if self.si:
            try:
                vim_connect.Disconnect(self.si)
                print("🛑 Disconnected from VMware.")
            except Exception:
                pass
        self.si = None

    def is_vmware_installed(self) -> bool:
        """Checks whether the necessary VMware SDK modules are available."""
        try:
            import pyVim.connect  # noqa: F401
            import pyVmomi.vim  # noqa: F401
            return True
        except ImportError:
            return False

    def list_vms(self) -> list[str]:
        """Retrieves a list of VMs on the ESXi/vCenter host."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return []

        content = self.si.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.VirtualMachine]
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive=True
        )
        vms = container_view.view
        return [vm.name for vm in vms]

    def create_vm(
        self,
        vm_name: str,
        datastore_name: str,
        guest_os: str,
        memory_mb: int = 1024,
        cpus: int = 1,
    ):
        """
        Creates a VM with specified configurations.
        """
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        content = self.si.RetrieveContent()
        datacenter = content.rootFolder.childEntity[0]
        vm_folder = datacenter.vmFolder
        resource_pool = datacenter.hostFolder.childEntity[0].resourcePool
        datastore = next(
            (ds for ds in datacenter.datastoreFolder.childEntity if ds.name == datastore_name),
            None,
        )
        if not datastore:
            print(f"⚠️ Datastore '{datastore_name}' not found.")
            return

        vm_cfg = vim.vm.ConfigSpec(
            name=vm_name,
            memoryMB=memory_mb,
            numCPUs=cpus,
            guestId=guest_os,
            files=vim.vm.FileInfo(vmPathName=f"[{datastore_name}]")
        )
        task = vm_folder.CreateVM_Task(config=vm_cfg, pool=resource_pool)
        print(f"🚀 Creating VM '{vm_name}'... Task initiated.")
        return task

    def power_on_vm(self, vm_name: str):
        """Powers on a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.PowerOnVM_Task()
            print(f"🔌 Powering on '{vm_name}'... Task initiated.")
            return task
        print(f"⚠️ VM '{vm_name}' not found.")

    def power_off_vm(self, vm_name: str):
        """Powers off a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.PowerOffVM_Task()
            print(f"⛔ Powering off '{vm_name}'... Task initiated.")
            return task
        print(f"⚠️ VM '{vm_name}' not found.")

    def delete_vm(self, vm_name: str):
        """Deletes a VM."""
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return

        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.Destroy_Task()
            print(f"🗑️ Deleting '{vm_name}'... Task initiated.")
            return task
        print(f"⚠️ VM '{vm_name}' not found.")

    def _get_vm_by_name(self, vm_name: str) -> vim.VirtualMachine | None:
        content = self.si.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.VirtualMachine]
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive=True
        )
        for vm in container_view.view:
            if vm.name == vm_name:
                return vm
        return None

# Example Usage:
if __name__ == "__main__":
    vmware = VMWareInterface(
        host="your-vmware-host",
        user="your-username",
        password="your-password"
    )
    if not vmware.is_vmware_installed():
        print("❌ VMware SDK not installed.")
    elif vmware.connect():
        print("Available VMs:", vmware.list_vms())
        # vmware.create_vm(vm_name="Automoy-VM", datastore_name="datastore1", guest_os="otherGuest")
