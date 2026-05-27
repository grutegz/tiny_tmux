import os
import sys
import tty
import termios
import select
import shutil
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

SAVE_CURSOR = b"\x1b7"
RESTORE_CURSOR = b"\x1b8"
REVERSE_VIDEO = b"\x1b[7m"
RESET_FMT = b"\x1b[0m"

class Multiplexer:
    """Оболочка для управления сессиями"""
    def __init__(self, command="/bin/bash"):
        self.command = command
        self.sessions = []
        self.active_index = 0
        self.prefix_mode = False
        self.old_tty_settings = None
        self.running = True
        self._create_session()

    def _create_session(self):
        """Создает новую сессию"""
        session = TerminalSession(self.command)
        session.start()
        
        columns, rows = shutil.get_terminal_size()
        session.set_window_size(rows - 1, columns)
        
        self.sessions.append(session)
        self.active_index = len(self.sessions) - 1

    def _delete_session(self, index):
        """Удаляет сессию по индексу"""
        session = self.sessions.pop(index)
        session.terminate()
        
        if not self.sessions:
            self.running = False
        else:
            self.active_index = min(self.active_index, len(self.sessions) - 1)
            self._redraw_screen()

    def run(self):
        """Настраивает терминал и запускает главный цикл"""
        self.old_tty_settings = termios.tcgetattr(STDIN_FD)
        try:
            tty.setraw(STDIN_FD)
            self._redraw_screen()
            self._event_loop()
        finally:
            self._cleanup()

    def _event_loop(self):
        """Главный цикл ввода-вывода"""
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
                        self._draw_status_bar()

            if not self.running:
                break

            if STDIN_FD in ready_to_read:
                user_input = os.read(STDIN_FD, BUFFER_SIZE)
                if not user_input:
                    self.running = False
                    break
                self._handle_input(user_input)

    def _handle_input(self, data):
        """Обработчик ввода"""
        if self.prefix_mode:
            self.prefix_mode = False
            if data == NEXT_KEY:
                self.active_index = (self.active_index + 1) % len(self.sessions)
                self._redraw_screen()
            elif data == PREV_KEY:
                self.activze_index = (self.active_index - 1) % len(self.sessions)
                self._redraw_screen()
            elif data == CREATE_KEY:
                self._create_session()
                self._redraw_screen()
            elif data == DELETE_KEY:
                self._delete_session(self.active_index)
            elif data == QUIT_KEY:
                self.running = False
            else:
                self._draw_status_bar()
            return

        if data == PREFIX_KEY:
            self.prefix_mode = True
            self._draw_status_bar()
        elif self.sessions:
            active_session = self.sessions[self.active_index]
            active_session.write_input(data)

    def _draw_status_bar(self):
        if not self.running or not self.sessions:
            return
            
        columns, rows = shutil.get_terminal_size()
        prefix_indicator = "[PREFIX]" if self.prefix_mode else "        "
        status_text = f" TINY TMUX | session {self.active_index + 1}/{len(self.sessions)} | {prefix_indicator} | C-b n/p c/d q "
        status_text = status_text.ljust(columns)
        
        move_to_bottom = f"\x1b[{rows};1H".encode("ascii")
        
        status_seq = (
            SAVE_CURSOR + 
            move_to_bottom + 
            REVERSE_VIDEO + 
            status_text.encode("utf-8") + 
            RESET_FMT + 
            RESTORE_CURSOR
        )
        os.write(STDOUT_FD, status_seq)

    def _redraw_screen(self):
        if not self.running or not self.sessions:
            return
        os.write(STDOUT_FD, CLEAR_SCREEN_SEQ)
        
        active_session = self.sessions[self.active_index]
        if active_session.screen_buffer:
            os.write(STDOUT_FD, active_session.screen_buffer)
            
        self._draw_status_bar()

    def _cleanup(self):
        for session in self.sessions:
            session.terminate()
        self.sessions.clear()
        termios.tcsetattr(STDIN_FD, termios.TCSADRAIN, self.old_tty_settings)
        os.write(STDOUT_FD, EXIT_SEQ)