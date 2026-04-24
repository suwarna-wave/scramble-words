from __future__ import annotations

import json
import math
import random
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_VENV_SITE_PACKAGES = sorted(PROJECT_ROOT.glob("sushma/lib/python*/site-packages"))

try:
    import pygame
except ModuleNotFoundError:
    for site_packages in LOCAL_VENV_SITE_PACKAGES:
        site_path = str(site_packages)
        if site_path not in sys.path:
            sys.path.insert(0, site_path)
        try:
            import pygame
            break
        except ModuleNotFoundError:
            continue
    else:
        print("This game requires pygame. Install it with: pip install -r requirements.txt")
        raise


WIDTH, HEIGHT = 1120, 720
FPS = 60
WORD_BANK_PATH = PROJECT_ROOT / "word_bank.txt"
SCORE_FILE_PATH = PROJECT_ROOT / "scores.json"

BG_TOP = (17, 28, 46)
BG_BOTTOM = (8, 14, 25)
PANEL = (245, 247, 250)
PANEL_ALT = (230, 236, 242)
TEXT_DARK = (26, 33, 43)
TEXT_MUTED = (90, 102, 118)
PRIMARY = (29, 122, 84)
PRIMARY_HOVER = (23, 103, 71)
ACCENT = (233, 155, 44)
ACCENT_SOFT = (255, 239, 209)
ERROR = (191, 58, 48)
SUCCESS = (29, 122, 84)
WHITE = (255, 255, 255)

LEVELS = {
    "Level 1": 60,
    "Level 2": 45,
    "Level 3": 25,
}

MIN_CUSTOM_TIME = 15
MAX_CUSTOM_TIME = 120


def draw_vertical_gradient(surface: pygame.Surface, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    for y in range(surface.get_height()):
        ratio = y / max(surface.get_height() - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def scramble_word(word: str) -> str:
    letters = list(word)
    for _ in range(12):
        random.shuffle(letters)
        scrambled = "".join(letters)
        if scrambled != word:
            return scrambled
    if len(word) > 1:
        return word[1:] + word[0]
    return word


@dataclass
class WordRound:
    original: str
    scrambled: str


class Button:
    def __init__(self, rect: pygame.Rect, text: str, kind: str = "primary") -> None:
        self.rect = rect
        self.text = text
        self.kind = kind

    def draw(self, surface: pygame.Surface, fonts: dict[str, pygame.font.Font], mouse_pos: tuple[int, int]) -> None:
        hovered = self.rect.collidepoint(mouse_pos)
        if self.kind == "primary":
            color = PRIMARY_HOVER if hovered else PRIMARY
            text_color = WHITE
        elif self.kind == "secondary":
            color = (214, 220, 228) if hovered else PANEL_ALT
            text_color = TEXT_DARK
        else:
            color = (235, 215, 212) if hovered else (244, 228, 225)
            text_color = ERROR

        pygame.draw.rect(surface, color, self.rect, border_radius=18)
        label = fonts["button"].render(self.text, True, text_color)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, event: pygame.event.Event) -> bool:
        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos)


class ScrambledWordsGame:
    def __init__(self) -> None:
        pygame.init()
        self.audio_enabled = self.init_audio()
        pygame.display.set_caption("Scrambled Words")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True

        self.fonts = {
            "hero": pygame.font.SysFont("georgia", 56, bold=True),
            "title": pygame.font.SysFont("georgia", 36, bold=True),
            "scramble": pygame.font.SysFont("consolas", 54, bold=True),
            "section": pygame.font.SysFont("verdana", 24, bold=True),
            "body": pygame.font.SysFont("verdana", 20),
            "small": pygame.font.SysFont("verdana", 16),
            "button": pygame.font.SysFont("verdana", 20, bold=True),
            "input": pygame.font.SysFont("verdana", 26),
            "stat": pygame.font.SysFont("verdana", 26, bold=True),
        }

        self.words = self.load_words()
        self.best_score = self.load_best_score()
        self.sounds = self.build_sounds()
        self.state = "menu"
        self.message = "Unscramble the word before the timer runs out."
        self.message_color = TEXT_MUTED
        self.level_name = "Level 2"
        self.selected_time = LEVELS[self.level_name]
        self.custom_time_input = str(self.selected_time)
        self.answer_input = ""
        self.score = 0
        self.correct_count = 0
        self.time_left = float(self.selected_time)
        self.round_started_at = 0
        self.current_round = self.pick_round()

        self.level_buttons = [
            Button(pygame.Rect(115 + i * 180, 280, 165, 54), name, "secondary")
            for i, name in enumerate(LEVELS.keys())
        ]
        self.start_button = Button(pygame.Rect(115, 535, 220, 58), "Start Game")
        self.reset_button = Button(pygame.Rect(355, 535, 210, 58), "Reset", "secondary")
        self.exit_button = Button(pygame.Rect(585, 535, 150, 58), "Quit", "danger")
        self.custom_minus_button = Button(pygame.Rect(115, 390, 50, 48), "-", "secondary")
        self.custom_plus_button = Button(pygame.Rect(325, 390, 50, 48), "+", "secondary")
        self.play_again_button = Button(pygame.Rect(95, 560, 250, 60), "Play Again")
        self.menu_button = Button(pygame.Rect(370, 560, 220, 60), "Main Menu", "secondary")
        self.back_button = Button(pygame.Rect(875, 55, 160, 50), "Menu", "secondary")

        self.answer_box = pygame.Rect(115, 525, 560, 56)
        self.custom_time_box = pygame.Rect(180, 390, 135, 48)

    def load_words(self) -> list[str]:
        if not WORD_BANK_PATH.exists():
            raise FileNotFoundError(f"Word bank not found: {WORD_BANK_PATH}")
        words = []
        seen = set()
        for line in WORD_BANK_PATH.read_text(encoding="utf-8").splitlines():
            word = line.strip().lower()
            if 4 <= len(word) <= 10 and word.isalpha() and word not in seen:
                seen.add(word)
                words.append(word)
        if len(words) < 2000:
            raise ValueError("Word bank must contain at least 2000 usable words.")
        return words

    def init_audio(self) -> bool:
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1)
            return True
        except pygame.error:
            return False

    def build_tone(self, frequency: int, duration_ms: int, volume: float = 0.35) -> pygame.mixer.Sound | None:
        if not self.audio_enabled:
            return None

        sample_rate = 44100
        total_samples = int(sample_rate * duration_ms / 1000)
        fade_samples = min(total_samples // 8, 400)
        buffer = array("h")

        for i in range(total_samples):
            envelope = 1.0
            if fade_samples:
                if i < fade_samples:
                    envelope = i / fade_samples
                elif i > total_samples - fade_samples:
                    envelope = max(0.0, (total_samples - i) / fade_samples)
            value = math.sin(2 * math.pi * frequency * (i / sample_rate))
            buffer.append(int(32767 * volume * envelope * value))

        return pygame.mixer.Sound(buffer=buffer)

    def build_sounds(self) -> dict[str, pygame.mixer.Sound | None]:
        return {
            "correct": self.build_tone(720, 140, 0.30),
            "wrong": self.build_tone(220, 320, 0.30),
            "start": self.build_tone(520, 180, 0.22),
        }

    def play_sound(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def load_best_score(self) -> int:
        if not SCORE_FILE_PATH.exists():
            return 0
        try:
            data = json.loads(SCORE_FILE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        value = data.get("best_score", 0)
        return value if isinstance(value, int) and value >= 0 else 0

    def save_best_score(self) -> None:
        payload = {"best_score": self.best_score}
        try:
            SCORE_FILE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    def pick_round(self) -> WordRound:
        word = random.choice(self.words)
        return WordRound(original=word, scrambled=scramble_word(word))

    def start_game(self, seconds: int | None = None) -> None:
        self.selected_time = seconds or self.selected_time
        self.time_left = float(self.selected_time)
        self.score = 0
        self.correct_count = 0
        self.answer_input = ""
        self.current_round = self.pick_round()
        self.message = "Game started. Type the correct word and press Enter."
        self.message_color = TEXT_MUTED
        self.state = "playing"
        self.round_started_at = pygame.time.get_ticks()
        self.play_sound("start")

    def reset_to_menu(self) -> None:
        self.state = "menu"
        self.answer_input = ""
        self.time_left = float(self.selected_time)
        self.current_round = self.pick_round()
        self.message = "Choose a level or set your own timer."
        self.message_color = TEXT_MUTED

    def fail_round(self, reason: str) -> None:
        self.best_score = max(self.best_score, self.score)
        self.save_best_score()
        self.state = "game_over"
        self.message = reason
        self.message_color = ERROR
        self.play_sound("wrong")

    def submit_answer(self) -> None:
        guess = self.answer_input.strip().lower()
        if not guess:
            self.message = "Type an answer before submitting."
            self.message_color = ERROR
            return

        if guess == self.current_round.original:
            self.score += len(self.current_round.original) * 10
            self.correct_count += 1
            previous_best = self.best_score
            self.best_score = max(self.best_score, self.score)
            if self.best_score != previous_best:
                self.save_best_score()
            self.current_round = self.pick_round()
            self.answer_input = ""
            self.time_left = float(self.selected_time)
            self.round_started_at = pygame.time.get_ticks()
            self.message = "Correct. Next word loaded."
            self.message_color = SUCCESS
            self.play_sound("correct")
        else:
            self.fail_round(f"Wrong answer. The word was '{self.current_round.original}'.")

    def update_timer(self) -> None:
        now = pygame.time.get_ticks()
        elapsed_ms = now - self.round_started_at
        self.time_left = max(0.0, self.selected_time - elapsed_ms / 1000)
        if self.time_left <= 0:
            self.fail_round(f"Time up. The word was '{self.current_round.original}'.")

    def handle_menu_event(self, event: pygame.event.Event) -> None:
        for idx, button in enumerate(self.level_buttons):
            if button.clicked(event):
                self.level_name = list(LEVELS.keys())[idx]
                self.selected_time = LEVELS[self.level_name]
                self.custom_time_input = str(self.selected_time)
                self.message = f"{self.level_name} selected."
                self.message_color = TEXT_MUTED

        if self.custom_minus_button.clicked(event):
            value = clamp(int(self.custom_time_input or self.selected_time) - 5, MIN_CUSTOM_TIME, MAX_CUSTOM_TIME)
            self.custom_time_input = str(value)
        elif self.custom_plus_button.clicked(event):
            value = clamp(int(self.custom_time_input or self.selected_time) + 5, MIN_CUSTOM_TIME, MAX_CUSTOM_TIME)
            self.custom_time_input = str(value)
        elif self.start_button.clicked(event):
            custom_time = self.parse_custom_time()
            if custom_time is None:
                self.message = f"Enter a time between {MIN_CUSTOM_TIME} and {MAX_CUSTOM_TIME} seconds."
                self.message_color = ERROR
            else:
                matched_level = next((name for name, seconds in LEVELS.items() if seconds == custom_time), None)
                self.level_name = matched_level or "Custom"
                self.start_game(custom_time)
        elif self.reset_button.clicked(event):
            self.level_name = "Level 2"
            self.selected_time = LEVELS[self.level_name]
            self.custom_time_input = str(self.selected_time)
            self.message = "Settings reset to the standard timer."
            self.message_color = TEXT_MUTED
        elif self.exit_button.clicked(event):
            self.running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.custom_time_input = self.custom_time_input[:-1]
            elif event.unicode.isdigit() and len(self.custom_time_input) < 3:
                self.custom_time_input += event.unicode

    def handle_playing_event(self, event: pygame.event.Event) -> None:
        if self.back_button.clicked(event):
            self.reset_to_menu()
            return

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_RETURN:
            self.submit_answer()
        elif event.key == pygame.K_ESCAPE:
            self.reset_to_menu()
        elif event.key == pygame.K_BACKSPACE:
            self.answer_input = self.answer_input[:-1]
        else:
            if event.unicode.isalpha() and len(self.answer_input) < 14:
                self.answer_input += event.unicode.lower()

    def handle_game_over_event(self, event: pygame.event.Event) -> None:
        if self.play_again_button.clicked(event):
            self.start_game(self.selected_time)
        elif self.menu_button.clicked(event):
            self.reset_to_menu()

    def parse_custom_time(self) -> int | None:
        if not self.custom_time_input:
            return None
        value = int(self.custom_time_input)
        if MIN_CUSTOM_TIME <= value <= MAX_CUSTOM_TIME:
            return value
        return None

    def draw_card(self, rect: pygame.Rect) -> None:
        shadow = rect.move(0, 10)
        pygame.draw.rect(self.screen, (4, 8, 16, 70), shadow, border_radius=28)
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=28)

    def draw_header(self) -> None:
        hero = self.fonts["hero"].render("Scrambled Words", True, WHITE)
        subtitle = self.fonts["body"].render("Timed word puzzle. Pick a level or set your own timer.", True, (208, 219, 230))
        self.screen.blit(hero, (80, 46))
        self.screen.blit(subtitle, (84, 118))

    def draw_menu(self) -> None:
        card = pygame.Rect(90, 170, 940, 480)
        self.draw_card(card)

        title = self.fonts["title"].render("Choose Game Mode", True, TEXT_DARK)
        self.screen.blit(title, (115, 205))
        desc = self.fonts["body"].render("Standard levels: 60, 45, 25 seconds.", True, TEXT_MUTED)
        self.screen.blit(desc, (115, 242))

        mouse_pos = pygame.mouse.get_pos()
        for button in self.level_buttons:
            button.kind = "primary" if button.text == self.level_name else "secondary"
            button.draw(self.screen, self.fonts, mouse_pos)

        custom_label = self.fonts["section"].render("Custom Time", True, TEXT_DARK)
        custom_hint = self.fonts["small"].render(f"{MIN_CUSTOM_TIME} to {MAX_CUSTOM_TIME} seconds", True, TEXT_MUTED)
        self.screen.blit(custom_label, (115, 345))
        self.screen.blit(custom_hint, (115, 370))

        pygame.draw.rect(self.screen, WHITE, self.custom_time_box, border_radius=14)
        pygame.draw.rect(self.screen, PRIMARY if self.custom_time_box.collidepoint(mouse_pos) else PANEL_ALT, self.custom_time_box, 2, border_radius=14)
        custom_text = self.fonts["input"].render(self.custom_time_input or "0", True, TEXT_DARK)
        self.screen.blit(custom_text, (self.custom_time_box.x + 18, self.custom_time_box.y + 8))
        seconds_label = self.fonts["body"].render("seconds", True, TEXT_MUTED)
        self.screen.blit(seconds_label, (self.custom_time_box.right + 14, self.custom_time_box.y + 10))

        self.custom_minus_button.draw(self.screen, self.fonts, mouse_pos)
        self.custom_plus_button.draw(self.screen, self.fonts, mouse_pos)
        self.start_button.draw(self.screen, self.fonts, mouse_pos)
        self.reset_button.draw(self.screen, self.fonts, mouse_pos)
        self.exit_button.draw(self.screen, self.fonts, mouse_pos)

        sample_box = pygame.Rect(760, 280, 235, 240)
        pygame.draw.rect(self.screen, ACCENT_SOFT, sample_box, border_radius=22)
        sample_title = self.fonts["section"].render("Quick Rules", True, TEXT_DARK)
        self.screen.blit(sample_title, (782, 304))
        rules = [
            "1. A scrambled word appears.",
            "2. Type the original word.",
            "3. Press Enter to submit.",
            "4. Correct answers add points.",
            "5. Wrong answer ends the run.",
        ]
        for idx, line in enumerate(rules):
            text = self.fonts["small"].render(line, True, TEXT_DARK)
            self.screen.blit(text, (782, 344 + idx * 30))

        message = self.fonts["body"].render(self.message, True, self.message_color)
        self.screen.blit(message, (115, 610))

    def draw_playing(self) -> None:
        card = pygame.Rect(90, 170, 940, 480)
        self.draw_card(card)
        mouse_pos = pygame.mouse.get_pos()

        self.back_button.draw(self.screen, self.fonts, mouse_pos)

        timer_ratio = self.time_left / self.selected_time if self.selected_time else 0
        timer_width = int(350 * timer_ratio)
        title = self.fonts["title"].render("Unscramble The Word", True, TEXT_DARK)
        self.screen.blit(title, (115, 205))

        info = self.fonts["body"].render(f"Mode: {self.level_name}   Timer: {self.selected_time}s", True, TEXT_MUTED)
        self.screen.blit(info, (115, 248))
        bank = self.fonts["small"].render(f"Word bank: {len(self.words)} words", True, TEXT_MUTED)
        self.screen.blit(bank, (115, 276))

        pygame.draw.rect(self.screen, PANEL_ALT, pygame.Rect(115, 310, 350, 18), border_radius=9)
        pygame.draw.rect(self.screen, ACCENT, pygame.Rect(115, 310, timer_width, 18), border_radius=9)
        timer_text = self.fonts["stat"].render(f"{self.time_left:04.1f}s", True, TEXT_DARK)
        self.screen.blit(timer_text, (480, 298))

        scramble_box = pygame.Rect(115, 350, 885, 120)
        pygame.draw.rect(self.screen, ACCENT_SOFT, scramble_box, border_radius=26)
        scrambled_text = self.fonts["scramble"].render(self.current_round.scrambled.upper(), True, TEXT_DARK)
        self.screen.blit(scrambled_text, scrambled_text.get_rect(center=scramble_box.center))

        prompt = self.fonts["section"].render("Your Answer", True, TEXT_DARK)
        self.screen.blit(prompt, (115, 490))
        pygame.draw.rect(self.screen, WHITE, self.answer_box, border_radius=16)
        pygame.draw.rect(self.screen, PRIMARY, self.answer_box, 2, border_radius=16)
        answer_surface = self.fonts["input"].render(self.answer_input, True, TEXT_DARK)
        self.screen.blit(answer_surface, (self.answer_box.x + 16, self.answer_box.y + 10))

        hint = self.fonts["small"].render("Enter: submit   Esc: menu", True, TEXT_MUTED)
        self.screen.blit(hint, (115, 592))
        audio_text = "Sound: on" if self.audio_enabled else "Sound: unavailable"
        self.screen.blit(self.fonts["small"].render(audio_text, True, TEXT_MUTED), (115, 615))

        stat_card = pygame.Rect(710, 500, 290, 125)
        pygame.draw.rect(self.screen, PANEL_ALT, stat_card, border_radius=22)
        score_text = self.fonts["stat"].render(f"Score: {self.score}", True, TEXT_DARK)
        best_text = self.fonts["body"].render(f"Best score: {self.best_score}", True, TEXT_MUTED)
        solved_text = self.fonts["body"].render(f"Words solved: {self.correct_count}", True, TEXT_MUTED)
        self.screen.blit(score_text, (730, 518))
        self.screen.blit(best_text, (730, 560))
        self.screen.blit(solved_text, (730, 590))

        message = self.fonts["body"].render(self.message, True, self.message_color)
        self.screen.blit(message, (115, 652))

    def draw_game_over(self) -> None:
        card = pygame.Rect(90, 170, 940, 480)
        self.draw_card(card)
        mouse_pos = pygame.mouse.get_pos()

        title = self.fonts["title"].render("Round Over", True, TEXT_DARK)
        subtitle = self.fonts["body"].render("A wrong answer or timer expiry ends the current run.", True, TEXT_MUTED)
        self.screen.blit(title, (115, 205))
        self.screen.blit(subtitle, (115, 246))

        message = self.fonts["section"].render(self.message, True, self.message_color)
        self.screen.blit(message, (115, 305))

        stats_box = pygame.Rect(115, 360, 500, 130)
        pygame.draw.rect(self.screen, PANEL_ALT, stats_box, border_radius=22)
        self.screen.blit(self.fonts["stat"].render(f"Final score: {self.score}", True, TEXT_DARK), (145, 386))
        self.screen.blit(self.fonts["body"].render(f"Best score: {self.best_score}", True, TEXT_MUTED), (145, 430))
        self.screen.blit(self.fonts["body"].render(f"Words solved this run: {self.correct_count}", True, TEXT_MUTED), (145, 458))

        tips_box = pygame.Rect(675, 282, 300, 205)
        pygame.draw.rect(self.screen, ACCENT_SOFT, tips_box, border_radius=22)
        tips_title = self.fonts["section"].render("Tip", True, TEXT_DARK)
        self.screen.blit(tips_title, (700, 304))
        lines = [
            "Use the standard levels",
            "for balanced difficulty,",
            "or set a custom timer",
            "from the menu if you",
            "want longer practice.",
        ]
        for idx, line in enumerate(lines):
            self.screen.blit(self.fonts["body"].render(line, True, TEXT_DARK), (700, 340 + idx * 28))

        self.play_again_button.draw(self.screen, self.fonts, mouse_pos)
        self.menu_button.draw(self.screen, self.fonts, mouse_pos)

    def draw(self) -> None:
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        pygame.draw.circle(self.screen, (40, 67, 100), (980, 90), 140)
        pygame.draw.circle(self.screen, (24, 47, 76), (140, 665), 120)
        self.draw_header()

        if self.state == "menu":
            self.draw_menu()
        elif self.state == "playing":
            self.draw_playing()
        else:
            self.draw_game_over()

        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif self.state == "menu":
                    self.handle_menu_event(event)
                elif self.state == "playing":
                    self.handle_playing_event(event)
                else:
                    self.handle_game_over_event(event)

            if self.state == "playing":
                self.update_timer()

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    ScrambledWordsGame().run()
    sys.exit(0)
