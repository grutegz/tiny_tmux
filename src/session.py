import os
import pty
import signal
import fcntl
import termios
import struct

BUFFER_SIZE = 1024

class TerminalSession:
    """Класс, инкапсулириующий PTY"""
    def __init__(self, command="/bin/bash"):
        self.command = command
        self.master_fd = None
        self.pid = None
        self.screen_buffer = b""

    def start(self):
        self.pid, self.master_fd = pty.fork()
        if self.pid == 0:
            os.execlp(self.command, self.command)

    def set_window_size(self, rows, cols):
        if self.master_fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def read_output(self):
        """Читает данные из PTY и сохраняет их в буфер"""
        try:
            data = os.read(self.master_fd, BUFFER_SIZE)
            self.screen_buffer += data
            return data
        except OSError:
            return b""

    def write_input(self, data):
        try: 
            os.write(self.master_fd, data)
        except OSError:
            pass

    def terminate(self):
        """Закрывает файловый дескриптор и жестко убивает дочерний процесс"""
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGKILL)
                os.waitpid(self.pid, 0)
            except OSError:
                pass