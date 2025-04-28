"""
Terminal Process Manager for running commands in separate terminal windows.
"""
import logging
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

class TerminalProcess:
    """Represents a process running in a terminal window."""
    
    def __init__(self, process_id: int, command: List[str], terminal_id: int, cwd: str):
        """
        Initialize a terminal process.
        
        Args:
            process_id: The OS process ID
            command: The command that was executed
            terminal_id: The internal terminal ID
            cwd: The working directory
        """
        self.process_id = process_id
        self.command = command
        self.terminal_id = terminal_id
        self.cwd = cwd
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.return_code: Optional[int] = None
        self.output_file: Optional[str] = None
        
    @property
    def is_running(self) -> bool:
        """Check if the process is still running."""
        if self.end_time is not None:
            return False
            
        try:
            # Check if process is still running
            if platform.system() == "Windows":
                # Windows-specific check
                output = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {self.process_id}"], 
                    capture_output=True, 
                    text=True
                )
                return str(self.process_id) in output.stdout
            else:
                # Unix-like systems
                os.kill(self.process_id, 0)  # Signal 0 doesn't kill the process, just checks if it exists
                return True
        except (ProcessLookupError, OSError):
            # Process no longer exists
            self.end_time = time.time()
            return False
            
    @property
    def duration(self) -> float:
        """Get the duration of the process in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the process to a dictionary."""
        return {
            "terminal_id": self.terminal_id,
            "process_id": self.process_id,
            "command": " ".join(self.command),
            "cwd": self.cwd,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "return_code": self.return_code,
            "duration": self.duration,
            "is_running": self.is_running,
            "output_file": self.output_file
        }


class TerminalProcessManager:
    """Manages processes running in terminal windows."""
    
    def __init__(self):
        """Initialize the terminal process manager."""
        self.processes: Dict[int, TerminalProcess] = {}
        self.next_terminal_id = 1
        self.temp_dir = tempfile.mkdtemp(prefix="junit_writer_terminal_")
        logger.info(f"Initialized TerminalProcessManager with temp directory: {self.temp_dir}")
        
    def _get_terminal_command(self, command: List[str], title: str) -> List[str]:
        """
        Get the platform-specific command to open a new terminal window.
        
        Args:
            command: The command to run in the terminal
            title: The title for the terminal window
            
        Returns:
            The command to open a new terminal window
        """
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # Escape quotes in the command
            escaped_command = " ".join(command).replace('"', '\\"')
            return [
                "osascript", "-e", 
                f'tell app "Terminal" to do script "{escaped_command}"'
            ]
        elif system == "Windows":
            # For Windows, use start command with a title
            return [
                "cmd.exe", "/c", "start", 
                f"\"{title}\"", "cmd.exe", "/k", 
                " ".join(command)
            ]
        else:  # Linux and others
            # Try to detect the available terminal emulator
            terminals = [
                ["gnome-terminal", "--", "bash", "-c"],
                ["xterm", "-T", title, "-e"],
                ["konsole", "--noclose", "-e"],
                ["terminator", "-e"]
            ]
            
            for terminal in terminals:
                if subprocess.run(
                    ["which", terminal[0]], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                ).returncode == 0:
                    cmd_str = " ".join(command) + "; echo 'Press Enter to close...'; read"
                    return terminal + [cmd_str]
            
            # Fallback to xterm if nothing else is found
            return ["xterm", "-T", title, "-e", " ".join(command) + "; read"]
    
    def run_in_terminal(
        self, 
        command: List[str], 
        cwd: str, 
        title: str = "JUnit Writer Test", 
        capture_output: bool = True
    ) -> Tuple[int, str]:
        """
        Run a command in a new terminal window.
        
        Args:
            command: The command to run
            cwd: The working directory
            title: The title for the terminal window
            capture_output: Whether to capture the output to a file
            
        Returns:
            A tuple of (terminal_id, output_file_path)
        """
        terminal_id = self.next_terminal_id
        self.next_terminal_id += 1
        
        # Create a unique title with the terminal ID
        unique_title = f"{title} (ID: {terminal_id})"
        
        # Create an output file if capturing output
        output_file = None
        if capture_output:
            output_file = os.path.join(self.temp_dir, f"terminal_{terminal_id}_output.txt")
            # Modify the command to redirect output
            if platform.system() == "Windows":
                command = command + [f">{output_file}", "2>&1"]
            else:
                command = command + [f"| tee {output_file}"]
        
        # Get the terminal command
        terminal_command = self._get_terminal_command(command, unique_title)
        
        logger.info(f"Launching terminal {terminal_id} with command: {' '.join(command)}")
        logger.debug(f"Full terminal command: {' '.join(terminal_command)}")
        
        try:
            # Start the process
            process = subprocess.Popen(
                terminal_command,
                cwd=cwd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Create a TerminalProcess object
            terminal_process = TerminalProcess(
                process_id=process.pid,
                command=command,
                terminal_id=terminal_id,
                cwd=cwd
            )
            
            if output_file:
                terminal_process.output_file = output_file
                
            # Store the process
            self.processes[terminal_id] = terminal_process
            
            logger.info(f"Started terminal process with ID: {terminal_id}, PID: {process.pid}")
            
            return terminal_id, output_file or ""
            
        except Exception as e:
            logger.error(f"Error launching terminal: {e}")
            raise
    
    def get_process(self, terminal_id: int) -> Optional[TerminalProcess]:
        """
        Get a terminal process by ID.
        
        Args:
            terminal_id: The terminal ID
            
        Returns:
            The terminal process, or None if not found
        """
        return self.processes.get(terminal_id)
    
    def get_output(self, terminal_id: int) -> str:
        """
        Get the output from a terminal process.
        
        Args:
            terminal_id: The terminal ID
            
        Returns:
            The output from the process, or an empty string if not available
        """
        process = self.get_process(terminal_id)
        if not process or not process.output_file:
            return ""
            
        try:
            with open(process.output_file, "r") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading output file: {e}")
            return f"Error reading output: {e}"
    
    def kill_process(self, terminal_id: int) -> bool:
        """
        Kill a terminal process.
        
        Args:
            terminal_id: The terminal ID
            
        Returns:
            True if the process was killed, False otherwise
        """
        process = self.get_process(terminal_id)
        if not process:
            return False
            
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(process.process_id)])
            else:
                os.kill(process.process_id, 9)  # SIGKILL
                
            process.end_time = time.time()
            logger.info(f"Killed terminal process with ID: {terminal_id}")
            return True
        except Exception as e:
            logger.error(f"Error killing process: {e}")
            return False
    
    def list_processes(self) -> List[Dict[str, Any]]:
        """
        List all terminal processes.
        
        Returns:
            A list of process dictionaries
        """
        # Update the status of all processes
        for process in self.processes.values():
            if process.is_running:
                pass  # Just checking if it's running will update the status
                
        return [process.to_dict() for process in self.processes.values()]
    
    def cleanup(self):
        """Clean up all processes and temporary files."""
        # Kill all running processes
        for terminal_id in list(self.processes.keys()):
            self.kill_process(terminal_id)
            
        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")


# Create a singleton instance
terminal_manager = TerminalProcessManager()
