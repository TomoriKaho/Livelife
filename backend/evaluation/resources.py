"""Sample process RSS without confusing it with unique or GPU memory."""

import os
import threading


class MemorySampler:
    def __init__(self, embedding_pid=None):
        import psutil

        self.processes = {"client": psutil.Process(os.getpid())}
        if embedding_pid:
            self.processes["embedding_server"] = psutil.Process(embedding_pid)
        self.peaks = {name: 0 for name in self.processes}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        import psutil

        while True:
            for name, process in self.processes.items():
                try:
                    self.peaks[name] = max(self.peaks[name], process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
            if self.stop.wait(0.1):
                break

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
