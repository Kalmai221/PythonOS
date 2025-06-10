#!/usr/bin/env python3
import curses
import random
import time

# Tetris shapes
SHAPES = [
    [[1, 1, 1, 1]],  # I
    [[1, 1], [1, 1]],  # O
    [[0,1,0],[1,1,1]],  # T
    [[1,0,0],[1,1,1]],  # J
    [[0,0,1],[1,1,1]],  # L
    [[1,1,0],[0,1,1]],  # S
    [[0,1,1],[1,1,0]]   # Z
]

class Tetris:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.height = 20
        self.width = 10
        self.board = [[0]*self.width for _ in range(self.height)]
        self.score = 0
        self.level = 1
        self.tick = 0.5
        self.shape = None
        self.shape_pos = [0, 3]
        self.spawn_shape()
        self.gameover = False

    def spawn_shape(self):
        self.shape = random.choice(SHAPES)
        self.shape_pos = [0, self.width//2 - len(self.shape[0])//2]
        if self.collision(self.shape_pos[0], self.shape_pos[1], self.shape):
            self.gameover = True

    def collision(self, y, x, shape):
        for i, row in enumerate(shape):
            for j, val in enumerate(row):
                if val:
                    if x+j < 0 or x+j >= self.width or y+i >= self.height:
                        return True
                    if y+i >= 0 and self.board[y+i][x+j]:
                        return True
        return False

    def rotate(self, shape):
        return [list(row) for row in zip(*shape[::-1])]

    def freeze_shape(self):
        y, x = self.shape_pos
        for i, row in enumerate(self.shape):
            for j, val in enumerate(row):
                if val and y+i >= 0:
                    self.board[y+i][x+j] = 1
        self.clear_lines()
        self.spawn_shape()

    def clear_lines(self):
        new_board = [row for row in self.board if any(v == 0 for v in row)]
        lines_cleared = self.height - len(new_board)
        self.score += lines_cleared * 100
        for _ in range(lines_cleared):
            new_board.insert(0, [0]*self.width)
        self.board = new_board

    def move(self, dy, dx):
        y, x = self.shape_pos
        if not self.collision(y+dy, x+dx, self.shape):
            self.shape_pos = [y+dy, x+dx]
            return True
        elif dy == 1 and dx == 0:
            # hit bottom or block below, freeze
            self.freeze_shape()
            return False
        return True

    def rotate_shape(self):
        new_shape = self.rotate(self.shape)
        y, x = self.shape_pos
        if not self.collision(y, x, new_shape):
            self.shape = new_shape

    def draw(self):
        self.stdscr.clear()
        # Draw board
        for i, row in enumerate(self.board):
            for j, val in enumerate(row):
                if val:
                    self.stdscr.addstr(i, j*2, "[]")
                else:
                    self.stdscr.addstr(i, j*2, "  ")
        # Draw falling shape
        y, x = self.shape_pos
        for i, row in enumerate(self.shape):
            for j, val in enumerate(row):
                if val and y+i >= 0:
                    self.stdscr.addstr(y+i, (x+j)*2, "[]")
        # Draw score
        self.stdscr.addstr(0, self.width*2 + 2, f"Score: {self.score}")
        self.stdscr.refresh()

    def run(self):
        self.stdscr.nodelay(True)
        while not self.gameover:
            self.draw()
            key = self.stdscr.getch()
            if key == curses.KEY_LEFT:
                self.move(0, -1)
            elif key == curses.KEY_RIGHT:
                self.move(0, 1)
            elif key == curses.KEY_DOWN:
                self.move(1, 0)
            elif key == ord(' '):
                self.rotate_shape()
            elif key == ord('q'):
                break
            time.sleep(self.tick)
            self.move(1, 0)
        self.stdscr.nodelay(False)
        self.stdscr.addstr(self.height//2, self.width*2//2 - 5, "GAME OVER")
        self.stdscr.refresh()
        self.stdscr.getch()

def main():
    curses.wrapper(Tetris().run)

if __name__ == "__main__":
    main()

def execute():
    main()