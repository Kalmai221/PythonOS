import os
import random
import time
import sys
import tty
import termios
import select

# Constants for the game
WIDTH = 40
HEIGHT = 20
PADDLE_HEIGHT = 4
BALL_SPEED = 0.1

# Directional constants
UP = 'w'
DOWN = 's'
QUIT = 'q'

# Game state variables
ball_x = WIDTH // 2
ball_y = HEIGHT // 2
ball_dx = random.choice([-1, 1])
ball_dy = random.choice([-1, 1])

player_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2
ai_paddle_y = HEIGHT // 2 - PADDLE_HEIGHT // 2

player_score = 0
ai_score = 0

# Terminal settings
old_settings = None

def setup_terminal():
    global old_settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(fd)

def reset_terminal():
    global old_settings
    if old_settings:
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

# Function to print the game screen
def print_screen():
    global player_paddle_y, ai_paddle_y, ball_x, ball_y, player_score, ai_score

    clear_screen()

    # Print score
    print(f"Player: {player_score}  AI: {ai_score}")
    print()

    # Print the top border
    print('+' + '-' * WIDTH + '+')

    # Print the game area
    for y in range(HEIGHT):
        row = ['|'] + [' '] * WIDTH + ['|']

        # Player paddle (left side)
        if y >= player_paddle_y and y < player_paddle_y + PADDLE_HEIGHT:
            row[1] = '#'

        # AI paddle (right side)
        if y >= ai_paddle_y and y < ai_paddle_y + PADDLE_HEIGHT:
            row[WIDTH] = '#'

        # Ball position
        if y == ball_y and 1 <= ball_x <= WIDTH:
            row[ball_x] = 'O'

        print(''.join(row))

    # Print the bottom border
    print('+' + '-' * WIDTH + '+')
    print("Controls: W/S to move paddle, Q to quit")

# Handle key press for player movement (non-blocking)
def get_input():
    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        try:
            ch = sys.stdin.read(1).lower()
            return ch
        except:
            pass
    return None

# Move the AI paddle based on the ball's position
def ai_move():
    global ai_paddle_y

    # AI paddle center
    paddle_center = ai_paddle_y + PADDLE_HEIGHT // 2

    # Simple AI: move towards ball with some delay for realism
    if paddle_center < ball_y - 1:
        ai_paddle_y += 1
    elif paddle_center > ball_y + 1:
        ai_paddle_y -= 1

    # Ensure the AI doesn't go out of bounds
    ai_paddle_y = max(0, min(ai_paddle_y, HEIGHT - PADDLE_HEIGHT))

# Update ball position and handle collisions
def move_ball():
    global ball_x, ball_y, ball_dx, ball_dy, player_paddle_y, ai_paddle_y
    global player_score, ai_score

    # Move the ball
    ball_x += ball_dx
    ball_y += ball_dy

    # Ball hitting top or bottom walls
    if ball_y <= 0 or ball_y >= HEIGHT - 1:
        ball_dy *= -1
        ball_y = max(0, min(ball_y, HEIGHT - 1))  # Keep ball in bounds

    # Ball hitting player paddle (left side)
    if ball_x <= 1 and ball_dx < 0:
        if player_paddle_y <= ball_y < player_paddle_y + PADDLE_HEIGHT:
            ball_dx = abs(ball_dx)  # Always bounce right
            ball_x = 2  # Move ball away from paddle

    # Ball hitting AI paddle (right side)
    if ball_x >= WIDTH - 1 and ball_dx > 0:
        if ai_paddle_y <= ball_y < ai_paddle_y + PADDLE_HEIGHT:
            ball_dx = -abs(ball_dx)  # Always bounce left
            ball_x = WIDTH - 2  # Move ball away from paddle

    # Ball out of bounds - scoring
    if ball_x < 0:
        ai_score += 1
        reset_ball()
    elif ball_x > WIDTH:
        player_score += 1
        reset_ball()

# Reset the ball after scoring
def reset_ball():
    global ball_x, ball_y, ball_dx, ball_dy
    ball_x = WIDTH // 2
    ball_y = HEIGHT // 2
    ball_dx = random.choice([-1, 1])
    ball_dy = random.choice([-1, 1])

    # Brief pause after scoring
    time.sleep(1)

# Main game loop
def game_loop():
    global player_paddle_y

    setup_terminal()

    try:
        while True:
            print_screen()

            # Get player input (non-blocking)
            move = get_input()

            if move == QUIT:
                break
            elif move == UP and player_paddle_y > 0:
                player_paddle_y -= 1
            elif move == DOWN and player_paddle_y < HEIGHT - PADDLE_HEIGHT:
                player_paddle_y += 1

            ai_move()  # Move the AI
            move_ball()  # Move the ball

            time.sleep(BALL_SPEED)

    except KeyboardInterrupt:
        pass
    finally:
        reset_terminal()
        clear_screen()
        print(f"\nGame Over! Final Score - Player: {player_score}, AI: {ai_score}")

if __name__ == '__main__':
    game_loop()

def execute():
    game_loop()