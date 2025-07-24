import subprocess
import time
import os
import sys

# Assuming OmniParserInterface is in the same directory and provides config
from .omniparser_interface import OmniParserInterface

class OmniParserServerManager:
    def __init__(self):
        # This interface instance is used for launching and checking the server.
        self._interface = OmniParserInterface()
        # self.server_process will be populated by the interface's launch_server method
        # if this manager instance successfully starts the server.
        self.server_process = None

    def is_server_ready(self):
        # Check both the interface and direct HTTP request
        try:
            # First check the interface
            if self._interface._check_server_ready():
                print("[OmniParserServerManager] Server ready via interface check")
                return True
            
            # Also try direct check to the running server
            import requests
            resp = requests.get("http://127.0.0.1:8111/probe/", timeout=3)
            if resp.status_code == 200:
                print("[OmniParserServerManager] Server ready via direct check")
                return True
                
        except Exception as e:
            print(f"[OmniParserServerManager] Server check failed: {e}")
        
        return False

    def start_server(self, conda_env_name="automoy_env"): # Added conda_env_name parameter
        if self.is_server_ready():
            print("[OmniParserServerManager] Server already running (checked via interface).")
            # If the server is already running, this manager instance didn't start it.
            # The _interface.server_process might be None or belong to another context.
            # We return None to indicate this manager isn't "owning" a new process.
            return None

        print("[OmniParserServerManager] Attempting to launch OmniParser server via interface...")
        # The launch_server method handles finding conda, paths, and process creation.
        # It returns True on success (server ready), False on failure.
        # It also sets self._interface.server_process internally.
        
        # We can pass specific parameters to launch_server if needed, otherwise it uses defaults.
        # Example: self._interface.launch_server(conda_env="my_other_env", port=8112)
        
        # Using the provided conda_env_name
        if self._interface.launch_server(conda_env=conda_env_name):
            print("[OmniParserServerManager] OmniParser server launched successfully via interface.")
            # Store the process object started by the interface for potential management (e.g., stop_server)
            self.server_process = self._interface.server_process 
            return self.server_process 
        else:
            print("[OmniParserServerManager][ERROR] Failed to launch OmniParser server via interface.")
            self.server_process = None # Ensure it's None on failure
            return None

    def wait_for_server(self, timeout=60): # Increased default timeout
        # This method is typically called after start_server has returned a process
        # or if the server was expected to be already running.
        
        print("[OmniParserServerManager] Waiting for OmniParser server to become ready...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_server_ready():
                print("[OmniParserServerManager] OmniParser server is ready.")
                return True
            
            # If this manager instance started the server, check its process
            if self.server_process and self.server_process.poll() is not None:
                print("[OmniParserServerManager][ERROR] OmniParser server process terminated prematurely.")
                # Optionally, capture and log stderr/stdout from self.server_process here
                return False
            
            # If the server wasn't started by this instance, or self.server_process is None,
            # we rely purely on is_server_ready() and the timeout.
            
            print("[OmniParserServerManager] Server not ready yet, waiting...")
            time.sleep(2)
            
        print("[OmniParserServerManager][ERROR] Timeout waiting for OmniParser server to become ready.")
        return False

    def get_interface(self):
        # Returns the OmniParserInterface instance, which can be used for parsing.
        return self._interface

    def stop_server(self):
        print("[OmniParserServerManager] Attempting to stop OmniParser server via interface...")
        # The interface's stop_server method handles the actual termination.
        self._interface.stop_server()
        # If this manager instance was tracking a process, clear it.
        if self.server_process:
            self.server_process = None
        print("[OmniParserServerManager] Stop command issued via interface.")

