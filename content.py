from world_objects import *
from pygame.sprite import Group
import pygame
from random import uniform


class Game:
    # responsible for switching between game modes:
    # 1) start menu - choosing between two options:
    # -- 1) new game (create new world)
    # -- 2) continue last game (if user didn't die when played last time and if user have played at least one game)
    # 2) world - game process
    def __init__(self, screen):
        # when game is initialized start menu is shown
        self.mode = StartMenu(self)
        self.screen = screen

    def tick(self, ticks):
        self.mode.tick(ticks)
        self.screen.blit(self.mode.image, (0, 0))

    def receive(self, event):
        # game reacts on events differently depending on current mode
        self.mode.receive(event)


class World:

    def __init__(self, game):
        self.objects = Group()
        self.mobs = Group()
        self.static = Group()
        self.monsters = Group()
        self.game = game

    def tick(self, ticks):
        if self.character.hp_level.hp < 1:
            self.delete()

        self.camera.adjust()
        self.image = self.camera.get_image(self.objects)

        x, y, w, h = self.camera.rect

        margin = to_px(Monster.speed_range[1]) + to_px(Monster.size_range[1])
        rect = Rect(x - margin, y - margin, w + 2 * margin, h + 2 * margin)

        # monsters tries to move only if they are within camera view
        # otherwise game might be lagging if there are a lot of objects on map
        monsters = Group(*filter(lambda obj: self.camera.rect.colliderect(obj.rect), self.monsters))

        # collision detection is done with objects within camera rect with margin
        cant_collide = Group(*filter(lambda obj: rect.colliderect(obj.rect), self.static))

        map_rect = self.camera.get_map_rect()

        self.character.try_to_move(cant_collide, map_rect)
        self.character.draw_hp(self.image)

        for monster in monsters:
            monster.draw_hp(self.image)
            if monster.rect.collidepoint(self.character.rect.center):  # if monster is close enough to attack character
                if monster.try_to_attack(self.character):
                    self.objects.add(BloodParticiple.get_participles(self.character.rect.center))

            monster.try_to_move_towards(self.character, cant_collide, map_rect)
        self.objects.update(ticks)
        pygame.display.flip()

    def save(self):
        with open(LAST_WORLD_FILE_NAME, 'w+') as file:
            file.writelines(map(lambda obj: obj.__repr__() + '\n', self.objects))

    def delete(self):
        if os.path.exists(LAST_WORLD_FILE_NAME):
            os.remove(LAST_WORLD_FILE_NAME)
        self.game.mode = StartMenu(self.game)

    def generate(self):
        map_bounds = Rect(0, 0, to_px(MAP_SIZE[0]), to_px(MAP_SIZE[1]))

        character = Character.get_random_object(map_bounds)
        self.character = character
        self.mobs.add(character)
        self.objects.add(character)

        monsters = Monster.get_random_objects(map_bounds, self.mobs)
        self.monsters.add(monsters)
        self.mobs.add(monsters)
        self.objects.add(monsters)

        for kind in [Stone, Tree]:
            objects = kind.get_random_objects(map_bounds, self.mobs)
            self.static.add(objects)
            self.objects.add(objects)

        self.camera = Camera(character, self.objects)

    def add(self, obj):
        self.objects.add(obj)
        if isinstance(obj, Mob):
            if isinstance(obj, Monster):
                self.monsters.add(obj)
            else:
                self.character = obj
        else:
            self.static.add(obj)

    def receive(self, event):

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_d:
                self.character.move_right(True)
            # влево
            elif event.key == pygame.K_a:
                self.character.move_left(True)
            # вверх
            elif event.key == pygame.K_w:
                self.character.move_up(True)
            # вниз
            elif event.key == pygame.K_s:
                self.character.move_down(True)

            elif event.key == pygame.K_RIGHT:
                self.character.inventory.choose_next()

            elif event.key == pygame.K_LEFT:
                self.character.inventory.choose_previous()

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_d:
                self.character.move_right(False)
            # влево
            elif event.key == pygame.K_a:
                self.character.move_left(False)
            # вверх
            elif event.key == pygame.K_w:
                self.character.move_up(False)
            # вниз
            elif event.key == pygame.K_s:
                self.character.move_down(False)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            for monster in spritecollide(self.character, self.monsters, False, collide_mask):
                if self.character.try_to_attack(monster):
                    self.objects.add(BloodParticiple.get_participles(monster.rect.center))

        elif event.type == pygame.MOUSEMOTION:
            angle = self.character.get_direction_to(*event.pos)
            if angle is not None:
                self.character.try_to_rotate(angle, self.static, self.camera.get_map_rect())

        elif event.type == pygame.QUIT:
            self.save()


class StartMenu:
    def get_btns_coords(self, button_width, button_height, screen_width, screen_height, number_of_buttons):
        # return  list of cords of left top corner of buttons
        screen_center = screen_width // 2
        x = screen_center - (button_width // 2)
        margin = (screen_height - number_of_buttons * button_height) / (number_of_buttons + 1)
        y = margin
        coords_list = []

        for _ in range(number_of_buttons):
            coords_list.append((x, y))
            y += button_height + margin

        return coords_list

    def __init__(self, game):
        self.game = game
        self.image = pygame.Surface(SCREEN_SIZE)
        self.image.fill('white')
        btn_w = SCREEN_SIZE[0] // 2
        btn_h = SCREEN_SIZE[1] // 6
        self.can_continue = last_world_exists()
        number = 2 if self.can_continue else 1
        btns_coords = self.get_btns_coords(btn_w, btn_h, *SCREEN_SIZE, number)
        self.new_btn = Button('New game', self.image, *btns_coords[0], btn_w, btn_h)
        if self.can_continue:
            self.continue_btn = Button('Continue last game', self.image, *btns_coords[1], btn_w, btn_h)

    def receive(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            cursor_pos = event.pos
            if self.new_btn.clicked(cursor_pos):
                world = World(self.game)
                world.generate()
                self.game.mode = world
            elif self.can_continue and self.continue_btn.clicked(cursor_pos):
                world = World(self.game)
                with open(LAST_WORLD_FILE_NAME, encoding='utf8') as file:
                    while True:
                        line = file.readline()
                        if line:
                            params = line.split()
                            for kind in [Stone, Tree, Monster, Character]:
                                if kind.__name__ == params[0]:
                                    world.add(kind(*map(int, params[1:])))
                                    break
                        else:
                            break
                world.camera = Camera(world.character, world.objects)
                self.game.mode = world

    def tick(self, ticks):
        pygame.display.flip()


class Camera:
    def __init__(self, follow, objects):
        w = CAMERA_VIEW_HEIGHT * SCREEN_SIZE[0] / SCREEN_SIZE[1]
        h = CAMERA_VIEW_HEIGHT
        self.rect = Rect(0, 0, to_px(w), to_px(h))
        self.x_on_map = 0
        self.y_on_map = 0
        self.follow = follow
        self.objects = objects
        self.adjust()
        rect_on_map = Rect(self.x_on_map, self.y_on_map, self.rect.w, self.rect.h)

    def update_coords_on_map(self):
        half_w, half_h = self.rect.w // 2, self.rect.h // 2
        self.x_on_map = min(to_px(MAP_SIZE[0]) - self.rect.w, max(0, self.follow.rect.centerx + self.x_on_map - half_w))
        self.y_on_map = min(to_px(MAP_SIZE[1]) - self.rect.h, max(0, self.follow.rect.centery + self.y_on_map - half_h))

    def adjust(self):
        prev_x_on_map, prev_y_on_map = self.x_on_map, self.y_on_map
        self.update_coords_on_map()
        dif_x, dif_y = self.x_on_map - prev_x_on_map, self.y_on_map - prev_y_on_map
        for obj in self.objects:
            obj.move(-dif_x, -dif_y)

    def get_map_rect(self):
        return Rect(-self.x_on_map, -self.y_on_map, to_px(MAP_SIZE[0]), to_px(MAP_SIZE[1]))

    def get_image(self, objects):
        image = pygame.Surface(SCREEN_SIZE)
        image.fill('#097969')
        objects.draw(image)
        return image


class Button(pygame.rect.Rect):
    def __init__(self, text, surface, x, y, w, h):
        super(Button, self).__init__(x, y, w, h)
        font = pygame.font.Font(None, h // 2)
        text = font.render(text, True, 'white')
        text_x = x + w // 2 - text.get_width() // 2
        text_y = y + h // 2 - text.get_height() // 2
        pygame.draw.rect(surface, 'gray', (x, y, w, h))
        surface.blit(text, (text_x, text_y))

    def clicked(self, cursor_pos):
        return self.collidepoint(*cursor_pos)


class BloodParticiple(Sprite):
    image = load_image('blood')
    size_range = 5, 20
    life_time_range = 0.7, 1.2
    radius = 100
    number = 10

    def __init__(self, x, y):
        super(BloodParticiple, self).__init__()
        size = randint(*self.__class__.size_range)
        resized = pygame.transform.scale(self.__class__.image, (size, size))
        self.v_direction = get_random_rotation()
        self.image = pygame.transform.rotate(resized, self.v_direction + 90)
        self.rect = self.image.get_rect().move(x - size // 2, y - size // 2)
        self.actual_coords = self.rect.x, self.rect.y
        self.max_life_time = uniform(*self.__class__.life_time_range)
        self.current_life_time = 0
        self.v = self.__class__.radius / self.max_life_time  # speed depends on lifetime of participle

    def update(self, ticks):
        ticks = ticks / 1000  # ticks are measured in milliseconds
        offset_x, offset_y = self.v * cos(self.v_direction) * ticks, self.v * -sin(self.v_direction) * ticks
        self.actual_coords = self.actual_coords[0] + offset_x, self.actual_coords[1] + offset_y
        self.rect = Rect(*self.actual_coords, *self.rect.size)
        self.current_life_time += ticks
        if self.current_life_time >= self.max_life_time:
            self.kill()

    @classmethod
    def get_participles(cls, coords):
        return Group([cls(*coords) for _ in range(cls.number)])

    def move(self, x_offset, y_offset):
        self.actual_coords = self.actual_coords[0] + x_offset, self.actual_coords[1] + y_offset
        self.rect = Rect(self.rect.x + x_offset, self.rect.y + y_offset, self.rect.w, self.rect.h)
