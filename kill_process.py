"""Kill processes on specific ports to clean up before restart."""
import subprocess
import os

def kill_process_on_port(port):
    """Kill process running on specified port."""
    try:
        if os.name == 'nt':  # Windows
            # Find process using the port
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True, capture_output=True, text=True
            )
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                pids = []
                for line in lines:
                    if 'LISTENING' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            pid = parts[-1]
                            pids.append(pid)
                
                # Kill each PID
                for pid in pids:
                    try:
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, check=True)
                        print(f"✓ Killed process {pid} on port {port}")
                    except subprocess.CalledProcessError:
                        print(f"✗ Failed to kill process {pid}")
            else:
                print(f"No process found on port {port}")
                
    except Exception as e:
        print(f"Error killing process on port {port}: {e}")

if __name__ == "__main__":
    print("Cleaning up processes...")
    kill_process_on_port(8001)  # GUI port
    kill_process_on_port(5100)  # OmniParser port
    print("Cleanup complete.")
