import atexit
import ssl
from typing import Optional, List
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

class VMWareInterface:
    def __init__(self, host: str, user: str, password: str, port: int = 443):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.si = None

    def connect(self) -> bool:
        context = ssl._create_unverified_context()
        try:
            self.si = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context,
            )
            atexit.register(Disconnect, self.si)
            print("✅ Connected to VMware vSphere/ESXi!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.si = None
            return False

    def disconnect(self) -> None:
        if self.si:
            try:
                Disconnect(self.si)
                print("🛑 Disconnected from VMware.")
            except Exception:
                pass
        self.si = None

    def is_vmware_installed(self) -> bool:
        try:
            import pyVim.connect  # noqa: F401
            import pyVmomi.vim  # noqa: F401
            return True
        except ImportError:
            return False

    def list_vms(self) -> List[str]:
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

    def wait_for_task(self, task):
        from pyVim.task import WaitForTask
        try:
            return WaitForTask(task)
        except Exception as e:
            print(f"❌ Task failed: {e}")

    def _get_vm_by_name(self, vm_name: str) -> Optional[vim.VirtualMachine]:
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

    def power_on_vm(self, vm_name: str):
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return
        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.PowerOnVM_Task()
            print(f"🔌 Powering on '{vm_name}'... Task initiated.")
            self.wait_for_task(task)
        else:
            print(f"⚠️ VM '{vm_name}' not found.")

    def power_off_vm(self, vm_name: str):
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return
        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.PowerOffVM_Task()
            print(f"⛔ Powering off '{vm_name}'... Task initiated.")
            self.wait_for_task(task)
        else:
            print(f"⚠️ VM '{vm_name}' not found.")

    def delete_vm(self, vm_name: str):
        if not self.si:
            print("❌ Not connected. Run `connect()` first.")
            return
        vm = self._get_vm_by_name(vm_name)
        if vm:
            task = vm.Destroy_Task()
            print(f"🗑️ Deleting '{vm_name}'... Task initiated.")
            self.wait_for_task(task)
        else:
            print(f"⚠️ VM '{vm_name}' not found.")

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
        # vmware.power_on_vm("YourVMName")
