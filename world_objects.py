from pygame.sprite import Sprite, spritecollideany, collide_mask, spritecollide, collide_rect, Group
from pygame import Rect, Surface
from pygame.mask import from_surface, Mask

from helpers import *
from constants import *
from math import hypot, sin, cos, radians, degrees, atan
from random import randint
from functools import reduce

SCREEN = pygame.display.set_mode(SCREEN_SIZE)


class WorldObject(Sprite):
    # image is loaded and mask is calculated in advance for each type of objects
    # and then resized for each individual object
    # it significantly accelerates the process of loading a world and collision detection
    image = Surface((100, 100))
    mask = from_surface(image)
    # size is measured in game units.
    # game units are converted to pixels with special function.
    # this way we can easily change game params and don't have to work with large numbers
    # as it would be if params were measured in px
    size_range = (0.5, 2)
    number_of_objects = 1

    def __init__(self, x, y, size):
        super(WorldObject, self).__init__()
        size = (size, size)  # width of every image of object is equal to its height
        self.rect = Rect(x, y, *size)
        self.image = pygame.transform.scale(self.__class__.image, size)
        self.mask = self.__class__.mask.scale(size)

    def move(self, x_offset, y_offset):
        self.rect = Rect(self.rect.x + x_offset, self.rect.y + y_offset, self.rect.w, self.rect.h)

    def w(self):
        return self.rect[-2]

    def h(self):
        return self.rect[-1]

    def x(self):
        return self.rect[0]

    def y(self):
        return self.rect[1]

    def coords(self):
        return self.x(), self.y()

    def current_coords_are_correct(self, objects_to_check_collision, map_rect):
        # check if object is within map and doesn't collide other objects
        collides = spritecollideany(self, objects_to_check_collision, collide_mask)
        return self.within_rect(map_rect) and not collides

    def within_rect(self, rect):
        return rect.contains(self.rect)

    @classmethod
    def get_random_objects(cls, map_rect, objects_to_check_collision=Group()):
        return Group(
            *[cls.get_random_object(map_rect, objects_to_check_collision) for _ in range(cls.number_of_objects)])

    @classmethod
    def get_random_object(cls, map_rect, objects_to_check_collision=Group()):
        obj = cls(*cls.get_random_initial_params())
        if obj.current_coords_are_correct(objects_to_check_collision, map_rect):
            return obj
        # is called recursively until object has correct params
        return cls.get_random_object(map_rect, objects_to_check_collision)

    @classmethod
    def get_random_initial_params(cls):
        min_size, max_size = cls.size_range
        size = randint(to_px(min_size), to_px(max_size))
        # object should be fully within map, so we need to subtract size of object from map borders
        x, y = randint(0, to_px(MAP_SIZE[0]) - size), randint(0, to_px(MAP_SIZE[1]) - size)
        return x, y, size

    def __repr__(self):
        # method is used when world is saved
        # by these params object can be recreated
        # so when user continues last game object has same properties
        return f'{self.__class__.__name__} {self.x()} {self.y()} {self.w()}'


class Mob(WorldObject):
    hp_color = 'red'
    v = 1  # units per second
    damage = 0
    attack_speed = 1  # seconds
    max_hp = 0

    def __init__(self, x, y, size, hp, max_hp):
        super(Mob, self).__init__(x, y, size)
        self.initial_image = self.image  # is used for rotation
        # (applying pygame.transform.rotate multiple times to the same image gives wrong result
        # so to get correctly rotated image we need to store not rotated one)
        self.view_direction = 90
        # direction is angle in degrees on unit circle (0 - right, 90 - top, 180 - left, 270 - bottom)
        # default images of mobs are drawn so direction of their sight is 90 degrees

        self.speed_direction = None  # mob isn't moving
        self.hp_level = HealthLevel(hp, max_hp, self.__class__.hp_color)
        self.attack_timer = 0  # increases every tick
        # mob can attack only if attack timer is equal or greater than its attack speed
        self.speed = 1  # length of mob speed vector when it's moving
        self.actual_coords = self.coords()
        # if speed of mob is too low then it can move a very short distance every tick (less than 1 px)
        # in that case we should store float coordinates of mob (pygame.Rect can't work with float numbers)
        # otherwise mob won't move at all

    def __repr__(self):
        x = self.rect.centerx - self.initial_image.get_rect().centerx
        y = self.rect.centery - self.initial_image.get_rect().centery
        size = self.initial_image.get_size()[0]
        # to recreate a mob we also need to store its hp_level when user quits the game
        return f'{self.__class__.__name__} {x} {y} {size} {self.hp_level.hp} {self.hp_level.max_hp}'

    def try_to_rotate(self, new_angle, objects_to_check_collision, map_rect):
        old_params = self.image, self.mask, self.view_direction, self.rect, self.actual_coords
        old_x_center, old_y_center = self.rect.center
        # if after rotation mob collides objects, we need to set its params back

        # all default images of mobs are drawn so direction of their sight is 90 degrees
        # therefore to get angle by which initial image should be rotated
        # we need to subtract 90 from sight direction of mob:
        self.image = pygame.transform.rotate(self.initial_image, new_angle - 90)
        # pygame.transform.rotate changes size of the image,
        # so we need to change size of rect attribute after rotation as well:
        self.rect = Rect(self.x(), self.y(), *self.image.get_size())
        # after resizing center of rect changes
        # therefore we should recalculate coordinates of rect so position of center of object won't change:
        new_x_center, new_y_center = self.rect.center
        x_dif, y_dif = old_x_center - new_x_center, old_y_center - new_y_center
        self.move(x_dif, y_dif)
        self.mask = pygame.mask.from_surface(self.image)
        self.view_direction = new_angle
        if not self.current_coords_are_correct(objects_to_check_collision, map_rect):
            self.image, self.mask, self.view_direction, self.rect, self.actual_coords = old_params
            return False
        return True

    def try_to_move(self, objects_to_check_collision, map_rect):
        if self.speed_direction is not None:  # if mob is moving

            # if mob can't move exactly towards its speed direction,
            # its speed reflects from objects it collides with.
            # this way mob doesn't get stuck in other objects when it can't move through them.
            # difference between reflected speed direction and original speed direction
            # should be less than right angle
            # otherwise object bounces off other objects as a ball
            for offset in range(91):
                for angle in [self.speed_direction + offset, self.speed_direction - offset]:
                    dif_x = cos(radians(angle)) * self.speed / FPS
                    dif_y = -sin(radians(angle)) * self.speed / FPS
                    self.move(dif_x, dif_y)
                    if self.current_coords_are_correct(objects_to_check_collision, map_rect):
                        return True
                    self.move(-dif_x, -dif_y)
        return False

    def move(self, x_offset, y_offset):
        self.actual_coords = self.actual_coords[0] + x_offset, self.actual_coords[1] + y_offset
        self.rect = Rect(int(self.actual_coords[0]), int(self.actual_coords[1]), self.rect.w, self.rect.h)

    def try_to_attack(self, obj):
        if self.attack_timer >= self.__class__.attack_speed:
            obj.hp_level.reduce_hp_level(self.__class__.damage)
            if obj.hp_level.hp < 1:
                obj.kill()
            self.attack_timer = 0
            return True
        return False

    def update(self, ticks):
        self.attack_timer += ticks / 1000

    def draw_hp(self, surface):
        im = self.hp_level.image
        x = self.rect.centerx - im.get_rect().centerx
        y = self.y() - im.get_rect().h - 3
        surface.blit(im, (x, y))

    def get_direction_to(self, x, y):
        x_dif, y_dif = x - self.rect.centerx, self.rect.centery - y
        dist = hypot(x_dif, y_dif)
        # if dist is equal to 0, method returns None because object is already on these coordinates.
        if dist:
            cosine = x_dif / dist
            sine = y_dif / dist
            # calculate angle by its sine and cosine:
            if cosine:
                tg = sine / cosine
                angle = degrees(atan(tg))
                if cosine < 0 and sine < 0:
                    angle = angle - 180
                elif cosine < 0:
                    angle = angle + 180
            else:
                angle = 90 * sine
            return angle % 360


class Stone(WorldObject):
    image = load_image('stone')
    mask = from_surface(image)
    number_of_objects = 35
    size_range = (2, 4)


class Tree(WorldObject):
    image = load_image('tree')
    mask = from_surface(image)
    number_of_objects = 50
    size_range = (3, 5)


class Monster(Mob):
    image = load_image('monster')
    mask = from_surface(image)
    number_of_objects = 20
    size_range = 0.5, 4
    hp_range = 2, 20
    speed_range = 0.5, 1
    action_radius = 2
    damage = 2
    attack_speed = 3

    def __init__(self, x, y, size, hp, max_hp, speed):
        super(Monster, self).__init__(x, y, size, hp, max_hp)
        self.speed = speed
        self.attack_timer = randint(0, self.__class__.attack_speed)

    @classmethod
    def get_random_initial_params(cls):
        # speed and hp of monster depend on its size.
        # if mob is big, it has high hp level but low speed
        # if mob is small, it has low hp level but high speed
        x, y, size = super(Monster, cls).get_random_initial_params()
        min_size, max_size = cls.size_range
        k = (to_units(size) - min_size) / (max_size - min_size)
        min_hp, max_hp = cls.hp_range
        max_hp = int(k * (max_hp - min_hp) + min_hp)
        min_speed, max_speed = cls.speed_range
        speed = to_px((1 - k) * (max_speed - min_speed) + min_speed)
        return x, y, size, max_hp, max_hp, speed

    def __repr__(self):
        rep = super(Monster, self).__repr__()
        return f'{rep} {self.speed}'

    def try_to_move_towards(self, goal, objects_to_check_collision, map_rect):
        if self.speed_direction is not None and self.speed_direction != self.view_direction:
            self.try_to_rotate(self.speed_direction, objects_to_check_collision, map_rect)

        self_to_goal_line = *goal.rect.center, *self.rect.center
        obstacles = list(filter(lambda obj: obj.rect.clipline(*self_to_goal_line), objects_to_check_collision))
        # obstacles are objects that monster will collide if it moves straight towards goal

        self.speed_direction = self.get_direction_to(*goal.rect.center)
        if obstacles:
            # monster should bypass obstacles
            self.speed_direction = self.get_bypassing_direction(self.speed_direction, obstacles)

        return super(Monster, self).try_to_move(objects_to_check_collision, map_rect)

    def get_bypassing_direction(self, direction_to_goal, obstacles):
        masks_and_rects = map(lambda obj: (obj.mask, obj.rect), obstacles)

        def get_union_mask_and_rect(mask_and_rect1, mask_and_rect2):
            mask1, rect1 = mask_and_rect1
            mask2, rect2 = mask_and_rect2
            max_x = max(rect1.right, rect2.right)
            max_y = max(rect1.bottom, rect2.bottom)
            min_x = min(rect1.x, rect2.x)
            min_y = min(rect1.y, rect2.y)
            size = max_x - min_x, max_y - min_y
            mask = Mask(size)
            mask.draw(mask1, (rect1.x - min_x, rect1.y - min_y))
            mask.draw(mask2, (rect2.x - min_x, rect2.y - min_y))
            return mask, Rect(min_x, min_y, *size)

        # create single mask from all obstacles.
        # (finding bypassing direction is a lot faster using common mask than individual mask for each obstacle)
        union_mask, mask_rect = reduce(get_union_mask_and_rect, masks_and_rects)
        self_rect = self.initial_image.get_rect()
        margin = hypot(self_rect.w, self_rect.h)
        size = mask_rect.w + margin, mask_rect.h + margin
        mask_with_margin = union_mask.scale(size)
        old_rect = union_mask.get_rect()
        new_rect = mask_with_margin.get_rect()
        mask_x = mask_rect.x + old_rect.centerx - new_rect.centerx
        mask_y = mask_rect.y + old_rect.centery - new_rect.centery

        outline = mask_with_margin.outline()

        opposite = direction_to_goal - 180 if direction_to_goal >= 180 else direction_to_goal + 180
        min_border = min(opposite, direction_to_goal)
        max_border = max(opposite, direction_to_goal)

        angle1 = direction_to_goal
        angle1_offset = 0
        angle2 = direction_to_goal
        angle2_offset = 0
        for point in outline:
            x, y = point
            x, y = x + mask_x, y + mask_y
            if not self.rect.collidepoint(x, y):
                direction = self.get_direction_to(x, y)
                offset = get_angle_between(direction, direction_to_goal)
                if min_border < direction < max_border:
                    if angle1_offset < offset:
                        angle1 = direction
                        angle1_offset = get_angle_between(angle1, direction_to_goal)
                else:
                    if angle2_offset < offset:
                        angle2 = direction
                        angle2_offset = get_angle_between(angle2, direction_to_goal)
        return angle1 if angle1_offset < angle2_offset else angle2


class Character(Mob):
    image = load_image('character')
    mask = from_surface(image)
    size_range = (2, 2)
    action_radius = 3
    hp_color = 'green'
    max_hp = 15
    damage = 1
    speed = 2
    number_of_objects = 1

    def __init__(self, x, y, size, hp, max_hp):
        super(Character, self).__init__(x, y, size, hp, max_hp)
        self.speeds = {90: False, 180: False, 270: False, 0: False}
        # user can control speed direction of character using W, A, S, D
        # these keys correspond to top (90), left (180), bottom (270), right (0) directions
        self.speed = to_px(self.__class__.speed)
        self.number_of_frames = 9
        animation = pygame.transform.scale(self.__class__.image, (size * self.number_of_frames, size))
        self.frames = self.get_frames(animation)
        self.set_frame(0)
        self.rect = Rect(x, y, *self.image.get_size())
        self.actual_coords = self.coords()
        self.attacking = False

    @classmethod
    def get_random_initial_params(cls):
        params = super(Character, cls).get_random_initial_params()
        return *params, cls.max_hp, cls.max_hp

    def get_frames(self, sheet):
        size = sheet.get_size()[0] / self.number_of_frames
        frames = []
        for i in range(self.number_of_frames):
            frame_location = (size * i, 0)
            frames.append(sheet.subsurface(pygame.Rect(frame_location, self.rect.size)))
        return frames

    def set_frame(self, i):
        self.cur_frame = i
        self.initial_image = self.frames[i]
        self.image = pygame.transform.rotate(self.initial_image, self.view_direction - 90)
        self.mask = from_surface(self.image)

    def update(self, ticks):
        super(Character, self).update(ticks)
        if self.number_of_frames - 1 <= self.cur_frame <= self.number_of_frames + 6:
            self.cur_frame += 1
            # last frame of character attack animation should last longer
        elif self.cur_frame < self.number_of_frames - 1 and self.attacking:
            self.set_frame(self.cur_frame + 1)
        else:
            self.attacking = False
            self.set_frame(0)

    def try_to_attack(self, obj):
        can = super(Character, self).try_to_attack(obj)
        if can:
            self.attacking = True
        return can

    def within_rect(self, rect):
        # parent method works fast but not precisely because it checks by rect and not mask of object
        # for character accuracy is more important, so we need to redefine this method
        x, y, w, h = self.rect.clip(rect)
        rect_mask = Mask((w, h), True)
        # check if total number of pixels of object mask is equal to number of pixels of object mask within rect
        return self.mask.count() == rect_mask.overlap_area(self.mask, (self.x() - x, self.y() - y))

    def get_sum_of_speeds(self, angle1, angle2):
        # find angle between two angles
        if angle1 is None:
            angle = angle2
        elif angle2 is None:
            angle = angle1
        else:
            angle = (angle1 + angle2) // 2
            difference = abs(angle1 - angle2)
            if difference > 180:
                angle += 180
            elif difference == 180:
                angle = None
        return angle

    def update_speed(self):
        directions = [i for i in self.speeds if self.speeds[i]]
        self.speed_direction = None
        for direction in directions:
            self.speed_direction = self.get_sum_of_speeds(self.speed_direction, direction)

    def move_right(self, value: bool):
        self.speeds[0] = value
        self.update_speed()

    def move_up(self, value: bool):
        self.speeds[90] = value
        self.update_speed()

    def move_left(self, value: bool):
        self.speeds[180] = value
        self.update_speed()

    def move_down(self, value: bool):
        self.speeds[270] = value
        self.update_speed()


class HealthLevel():
    size = 50, 5

    def __init__(self, current_hp, max_hp, color):
        self.hp = current_hp
        self.color = color
        self.max_hp = max_hp
        self.update_image()

    def reduce_hp_level(self, hp_count):
        self.hp -= hp_count
        self.update_image()

    def update_image(self):
        self.image = pygame.Surface(self.__class__.size)
        self.image.fill('gray')
        max_w, max_h = self.__class__.size
        w = self.hp / self.max_hp * max_w
        self.image.fill(self.color, (0, 0, w, max_h))
