import os
import random
import time
import sys
import tty
import termios

# Constants for the game
WIDTH = 40
HEIGHT = 20
PADDLE_HEIGHT = 4
BALL_SPEED = 0.1

# Directional constants
UP = 'w'
DOWN = 's'

# Game state variables
ball_x = WIDTH // 2
ball_y = HEIGHT // 2
ball_dx = random.choice([-1, 1])
ball_dy = random.choice([-1, 1])

player_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2
ai_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2

# Setup terminal
def setup_terminal():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(fd)
    return old_settings

def reset_terminal(old_settings):
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

# Function to print the game screen
def print_screen():
    global player_paddle_y, ai_paddle_y, ball_x, ball_y

    clear_screen()

    # Print the top border
    print('+' + '-' * WIDTH + '+')

    # Print the game area
    for y in range(HEIGHT):
        row = '|'

        if y in range(player_paddle_y, player_paddle_y + PADDLE_HEIGHT):
            row += '#'
        else:
            row += ' '

        # Ball position
        if y == ball_y:
            row = row[:ball_x + 1] + 'O' + row[ball_x + 2:]

        if y in range(ai_paddle_y, ai_paddle_y + PADDLE_HEIGHT):
            row += '#'
        else:
            row += ' '

        row += '|'
        print(row)

    # Print the bottom border
    print('+' + '-' * WIDTH + '+')

# Handle key press for player movement
def get_input():
    fd = sys.stdin.fileno()
    old_settings = setup_terminal()

    try:
        ch = sys.stdin.read(1)
        if ch in [UP, DOWN]:
            return ch
    except:
        pass
    finally:
        reset_terminal(old_settings)
    return None

# Move the AI paddle based on the ball's position
def ai_move():
    global ai_paddle_y

    # AI paddle moves based on ball's Y position
    if ai_paddle_y + PADDLE_HEIGHT // 2 < ball_y:
        ai_paddle_y += 1
    elif ai_paddle_y + PADDLE_HEIGHT // 2 > ball_y:
        ai_paddle_y -= 1

    # Ensure the AI doesn't go out of bounds
    ai_paddle_y = max(0, min(ai_paddle_y, HEIGHT - PADDLE_HEIGHT))

# Update ball position and handle collisions
def move_ball():
    global ball_x, ball_y, ball_dx, ball_dy, player_paddle_y, ai_paddle_y

    # Move the ball
    ball_x += ball_dx
    ball_y += ball_dy

    # Ball hitting top or bottom
    if ball_y <= 0 or ball_y >= HEIGHT - 1:
        ball_dy *= -1

    # Ball hitting paddles
    if ball_x == 1 and player_paddle_y <= ball_y < player_paddle_y + PADDLE_HEIGHT:
        ball_dx *= -1

    if ball_x == WIDTH - 2 and ai_paddle_y <= ball_y < ai_paddle_y + PADDLE_HEIGHT:
        ball_dx *= -1

    # Ball out of bounds (left or right side)
    if ball_x <= 0 or ball_x >= WIDTH - 1:
        reset_game()

# Reset the game after scoring
def reset_game():
    global ball_x, ball_y, ball_dx, ball_dy, player_paddle_y, ai_paddle_y
    ball_x = WIDTH // 2
    ball_y = HEIGHT // 2
    ball_dx = random.choice([-1, 1])
    ball_dy = random.choice([-1, 1])
    player_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2
    ai_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2

# Main game loop
def game_loop():
    global player_paddle_y

    while True:
        print_screen()

        # Get player input
        move = get_input()

        if move == UP and player_paddle_y > 0:
            player_paddle_y -= 1
        elif move == DOWN and player_paddle_y < HEIGHT - PADDLE_HEIGHT:
            player_paddle_y += 1

        ai_move()  # Move the AI
        move_ball()  # Move the ball

        time.sleep(BALL_SPEED)

if __name__ == '__main__':
    try:
        game_loop()
    except KeyboardInterrupt:
        reset_terminal(None)
        print("\nGame Over!")

def execute():
    try:
        game_loop()
    except KeyboardInterrupt:
        reset_terminal(None)
        print("\nGame Over!")