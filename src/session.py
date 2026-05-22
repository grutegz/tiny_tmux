import os
import pty
import signal

BUFFER_SIZE = 1024

class TerminalSession:
    """Класс, инкапсулирующий процесс оболочки и его PTY."""

    def __init__(self, command="/bin/bash"):
        """Инициализирует базовые параметры сессии."""
        self.command = command
        self.master_fd = None
        self.pid = None
        self.screen_buffer = b""

    def start(self):
        """Создает PTY и запускает процесс."""
        self.pid, self.master_fd = pty.fork()
        if self.pid == 0:
            os.execlp(self.command, self.command)

    def read_output(self):
        """Читает данные из PTY и сохраняет их в буфер экрана."""
        try:
            data = os.read(self.master_fd, BUFFER_SIZE)
            self.screen_buffer += data
            return data
        except OSError:
            return b""

    def write_input(self, data):
        """Отправляет данные в PTY."""
        try:
            os.write(self.master_fd, data)
        except OSError:
            pass

    def terminate(self):
        """Закрывает файловый дескриптор и жестко убивает дочерний процесс."""
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