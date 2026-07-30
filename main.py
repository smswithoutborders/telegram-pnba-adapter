# SPDX-License-Identifier: GPL-3.0-only

from adapter import TelegramPNBAAdapter
from ipc_service import AdapterIPCService


def main():
    """Entry point for starting the Adapter's IPC service."""
    adapter = TelegramPNBAAdapter()
    service = AdapterIPCService(adapter)
    service.start()


if __name__ == "__main__":
    main()
