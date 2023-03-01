import os
from random import randint
from constants import *
import pygame


def load_image(name):
    fullname = os.path.join(IMAGES_DIRECTORY, name + '.png')  # all images have png format
    image = pygame.image.load(fullname).convert_alpha()
    return image


def get_random_rotation():
    return randint(0, 359)


def last_world_exists():
    return os.path.exists(LAST_WORLD_FILE_NAME)


def get_angle_between(angle1, angle2):
    dif = abs(angle1 - angle2)
    if dif > 180:
        dif = 360 - dif
    return dif


def to_px(units):
    return int(SCREEN_SIZE[1] / CAMERA_VIEW_HEIGHT * units)


def to_units(px):
    return CAMERA_VIEW_HEIGHT / SCREEN_SIZE[1] * px
