import pygame
from constants import FPS
from content import Game
from world_objects import SCREEN

# initializing game
if __name__ == '__main__':
    pygame.init()
    pygame.display.set_caption('Survivor')
    running = True
    clock = pygame.time.Clock()
    game = Game(SCREEN)
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.receive(event)
        game.tick(clock.tick(FPS))
    pygame.quit()
