import os
import sys
import tty
import termios
import select
from session import TerminalSession

STDIN_FD = sys.stdin.fileno()
STDOUT_FD = sys.stdout.fileno()
BUFFER_SIZE = 1024

PREFIX_KEY = b"\x02"
NEXT_KEY = b"n"
PREV_KEY = b"p"
QUIT_KEY = b"q"
CREATE_KEY = b"c"
DELETE_KEY = b"d"

CLEAR_SCREEN_SEQ = b"\x1b[2J\x1b[H"
EXIT_SEQ = b"\r\n"

class Multiplexer:
    """Оболочка для динамического управления массивом терминальных сессий."""

    def __init__(self, default_command="/bin/bash"):
        """Инициализирует мультиплексор, создавая первую дефолтную сессию."""
        self.default_command = default_command
        self.sessions = []
        self.active_index = 0
        self.prefix_mode = False
        self.old_tty_settings = None
        self.running = True
        self._create_session()

    def _create_session(self):
        """Создает новую сессию и делает её активной."""
        session = TerminalSession(self.default_command)
        session.start()
        self.sessions.append(session)
        self.active_index = len(self.sessions) - 1

    def _delete_session(self, index):
        """Завершает сессию по индексу и сдвигает указатель массива."""
        session = self.sessions.pop(index)
        session.terminate()
        
        if not self.sessions:
            self.running = False
        else:
            self.active_index = min(self.active_index, len(self.sessions) - 1)
            self._redraw_screen()

    def run(self):
        """Настраивает терминал и запускает главный цикл обработки."""
        self.old_tty_settings = termios.tcgetattr(STDIN_FD)
        try:
            tty.setraw(STDIN_FD)
            self._redraw_screen()
            self._event_loop()
        finally:
            self._cleanup()

    def _event_loop(self):
        """Главный цикл мультиплексирования ввода-вывода."""
        while self.running:
            master_fds = [s.master_fd for s in self.sessions]
            ready_to_read, _, _ = select.select([STDIN_FD] + master_fds, [], [])

            for session in list(self.sessions):
                if session.master_fd in ready_to_read:
                    data = session.read_output()
                    if not data:
                        if session in self.sessions:
                            self._delete_session(self.sessions.index(session))
                        continue
                    if self.sessions and session == self.sessions[self.active_index]:
                        os.write(STDOUT_FD, data)

            if not self.running:
                break

            if STDIN_FD in ready_to_read:
                user_input = os.read(STDIN_FD, BUFFER_SIZE)
                if not user_input:
                    self.running = False
                    break
                self._handle_input(user_input)

    def _handle_input(self, data):
        """Обрабатывает ввод пользователя и горячие клавиши управления."""
        if self.prefix_mode:
            self.prefix_mode = False
            if data == NEXT_KEY:
                self.active_index = (self.active_index + 1) % len(self.sessions)
                self._redraw_screen()
            elif data == PREV_KEY:
                self.active_index = (self.active_index - 1) % len(self.sessions)
                self._redraw_screen()
            elif data == CREATE_KEY:
                self._create_session()
                self._redraw_screen()
            elif data == DELETE_KEY:
                self._delete_session(self.active_index)
            elif data == QUIT_KEY:
                self.running = False
            return

        if data == PREFIX_KEY:
            self.prefix_mode = True
        elif self.sessions:
            active_session = self.sessions[self.active_index]
            active_session.write_input(data)

    def _redraw_screen(self):
        """Очищает экран и отрисовывает буфер активной сессии."""
        if not self.running or not self.sessions:
            return
        os.write(STDOUT_FD, CLEAR_SCREEN_SEQ)
        active_session = self.sessions[self.active_index]
        if active_session.screen_buffer:
            os.write(STDOUT_FD, active_session.screen_buffer)

    def _cleanup(self):
        """Завершает все сессии и восстанавливает настройки терминала."""
        for session in self.sessions:
            session.terminate()
        self.sessions.clear()
        termios.tcsetattr(STDIN_FD, termios.TCSADRAIN, self.old_tty_settings)
        os.write(STDOUT_FD, EXIT_SEQ)

def main():
    """Точка входа."""
    mux = Multiplexer(default_command="/bin/bash")
    mux.run()

if __name__ == "__main__":
    main()