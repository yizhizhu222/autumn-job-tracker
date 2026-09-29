"""One server process per data directory, even when ports differ."""
import os
from pathlib import Path

class DataLock:
    def __init__(self,directory):
        root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=True)
        self.file=(root/'.tracker.lock').open('a+b')
        self.file.seek(0,2)
        if not self.file.tell():self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise ValueError('该数据目录已有程序在运行，请使用已打开的看板或先关闭旧程序') from None
    def close(self):
        if not self.file.closed:self.file.close()
