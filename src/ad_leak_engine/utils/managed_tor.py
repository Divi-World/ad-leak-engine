"""Managed Tor Daemon [SEED: 2399].
Spawns and controls a local Tor instance programmatically.
Eliminates manual config dependencies and ensures ControlPort availability.
"""
import logging
import os
import sys
import subprocess
import time
import tempfile
import shutil
from typing import Optional
from stem import Signal
from stem.control import Controller
import psutil

logger = logging.getLogger(__name__)

class ManagedTorDaemon:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ManagedTorDaemon, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.process: Optional[subprocess.Popen] = None
        self.controller: Optional[Controller] = None
        self.socks_port = 9050
        self.control_port = 9051
        self.data_dir = None
        self._start_daemon()
        self._initialized = True

    def _find_tor_executable(self) -> str:
        """Locates the Tor executable bundled with Tor Browser or system PATH."""
        # Common paths for Windows Tor Browser Portable
        possible_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\TorBrowser\Tor Browser\Browser\TorBrowser\Tor\tor.exe"),
            r"tor",
        ]

        # Try to find it dynamically if standard paths fail
        for p in possible_paths:
            if os.path.exists(p):
                return p

        # Fallback: Assume 'tor' is in PATH (common in Linux/Mac dev envs)
        try:
            subprocess.run(["tor", "--version"], capture_output=True, check=True)
            return "tor"
        except Exception:
            raise FileNotFoundError("Tor executable not found. Please ensure Tor is installed.")

    def _start_daemon(self):
        """Starts a temporary Tor instance with ControlPort enabled."""
        logger.info("[TOR_DAEMON] Initializing Managed Tor Instance...")

        # Create temp dir for data to avoid permission issues
        self.data_dir = tempfile.mkdtemp(prefix="ale_tor_")
        tor_exe = self._find_tor_executable()

        # Build command with explicit ports
        cmd = [
            tor_exe,
            "--SocksPort", str(self.socks_port),
            "--ControlPort", str(self.control_port),
            "--DataDirectory", self.data_dir,
            "--CookieAuthentication", "0", # Disable cookie auth for simplicity
            "--HashedControlPassword", "", # No password
        ]

        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Wait for Tor to boot
            time.sleep(3)

            # Connect Controller
            self.controller = Controller.from_port(address="127.0.0.1", port=self.control_port)
            self.controller.authenticate()
            logger.info(f"[TOR_DAEMON] Started successfully. PID: {self.process.pid}")

        except Exception as e:
            logger.error(f"[TOR_DAEMON] Failed to start: {e}")
            self.cleanup()
            raise

    def rotate_circuit(self) -> bool:
        """Forces a new identity (IP change)."""
        if not self.controller:
            return False
        try:
            self.controller.signal(Signal.NEWNYM)
            time.sleep(2) # Allow circuit build
            logger.info("[TOR_DAEMON] Circuit rotated.")
            return True
        except Exception as e:
            logger.warning(f"[TOR_DAEMON] Rotation failed: {e}")
            return False

    def get_proxy_config(self) -> dict:
        return {
            "http": f"socks5h://127.0.0.1:{self.socks_port}",
            "https": f"socks5h://127.0.0.1:{self.socks_port}",
            "all": f"socks5h://127.0.0.1:{self.socks_port}"
        }

    def cleanup(self):
        """Stops the Tor process and removes temp files."""
        # Detach references BEFORE closing so a concurrent / re-entrant call
        # (e.g. __del__ firing while cleanup is running) is a no-op.
        ctrl = self.controller
        self.controller = None
        # During interpreter shutdown, stem's socket close races with Python's
        # own IO teardown and can segfault. Skip controller.close() at that
        # point — the OS reclaims the fd when the process exits.
        if ctrl is not None and not sys.is_finalizing():
            try:
                ctrl.close()
            except Exception:
                pass

        proc = self.process
        self.process = None
        if proc is not None:
            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
            except Exception:
                pass

        if self.data_dir and os.path.exists(self.data_dir):
            shutil.rmtree(self.data_dir, ignore_errors=True)
        logger.info("[TOR_DAEMON] Cleanup complete.")

    def __del__(self):
        # Only invoke cleanup if we still hold state — otherwise cleanup()
        # was already called explicitly and there is nothing to do. Wrap in
        # try/except so any shutdown-time surprise (e.g. partially-torn-down
        # logging) cannot crash the interpreter.
        if getattr(self, "_initialized", False) and (
            self.process is not None or self.controller is not None
        ):
            try:
                self.cleanup()
            except Exception:
                pass