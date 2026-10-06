import pygame
import math
import json
import time

try:
    import serial
except ImportError:
    serial = None

BG_COLOR = (24, 26, 32)
PANEL_COLOR = (33, 37, 43)
TEXT_COLOR = (220, 224, 232)
TEXT_MUTED = (171, 178, 191)
ACCENT_BLUE = (97, 175, 239)
ACCENT_HOVER = (110, 190, 255)
JOINT_GREEN = (152, 195, 121)
JOINT_RED = (224, 108, 117)
SUCCESS_GREEN = (96, 187, 129)
WARNING_ORANGE = (245, 169, 98)
DANGER_RED = (233, 95, 95)


class BluetoothSerialManager:
    def __init__(self):
        self.port = None
        self.connection = None
        self.connected = False
        self.last_error = ""

    def detect_port(self):
        if serial is None:
            self.last_error = "pyserial não está instalado."
            return None

        try:
            from serial.tools import list_ports
            ports = [p.device for p in list_ports.comports()]
            if not ports:
                self.last_error = "Nenhuma porta serial disponível."
                return None

            preferred = [p for p in ports if any(token in p.lower() for token in ("com", "bluetooth", "rfcomm"))]
            if preferred:
                return preferred[0]
            return ports[0]
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def connect(self, port=None):
        if serial is None:
            self.last_error = "pyserial não está instalado."
            return False

        target = port or self.detect_port()
        if not target:
            return False

        try:
            if self.connection and self.connection.is_open:
                self.connection.close()

            self.connection = serial.Serial(target, 115200, timeout=1)
            self.port = target
            self.connected = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.connected = False
            self.last_error = str(exc)
            return False

    def disconnect(self):
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
        self.connection = None
        self.port = None
        self.connected = False

    def send_payload(self, payload):
        if serial is None or not self.connected or self.connection is None or not self.connection.is_open:
            return False

        try:
            self.connection.write((json.dumps(payload) + "\n").encode("utf-8"))
            self.connection.flush()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.connected = False
            return False


class Slider:
    def __init__(self, x, y, w, min_val, max_val, start_val, label):
        self.rect = pygame.Rect(x, y, w, 8)
        self.min_val = min_val
        self.max_val = max_val
        self.val = start_val
        self.label = label

        self.knob_radius = 10
        self.update_knob_pos()
        self.active = False

    def update_knob_pos(self):
        fraction = (self.val - self.min_val) / (self.max_val - self.min_val)
        self.knob_x = self.rect.x + int(fraction * self.rect.w)

    def draw(self, screen, font):
        lbl_img = font.render(f"{self.label}: {int(self.val)}°", True, TEXT_COLOR)
        screen.blit(lbl_img, (self.rect.x, self.rect.y - 22))

        pygame.draw.rect(screen, (50, 54, 66), self.rect, border_radius=4)
        progress_w = self.knob_x - self.rect.x
        if progress_w > 0:
            pygame.draw.rect(screen, ACCENT_BLUE, (self.rect.x, self.rect.y, progress_w, 8), border_radius=4)

        color = ACCENT_HOVER if self.active else ACCENT_BLUE
        pygame.draw.circle(screen, color, (self.knob_x, self.rect.y + 4), self.knob_radius)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            distance = math.hypot(mouse_pos[0] - self.knob_x, mouse_pos[1] - (self.rect.y + 4))
            if distance <= self.knob_radius or self.rect.collidepoint(mouse_pos):
                self.active = True
                self.update_value(mouse_pos[0])
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.active = False
        elif event.type == pygame.MOUSEMOTION and self.active:
            self.update_value(event.pos[0])
            return True
        return False

    def update_value(self, mouse_x):
        mouse_x = max(self.rect.x, min(mouse_x, self.rect.x + self.rect.w))
        fraction = (mouse_x - self.rect.x) / self.rect.w
        self.val = self.min_val + fraction * (self.max_val - self.min_val)
        self.knob_x = int(mouse_x)


class Button:
    def __init__(self, x, y, w, h, text, callback_data):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback_data = callback_data
        self.is_hovered = False

    def draw(self, screen, font):
        color = PANEL_COLOR if not self.is_hovered else (45, 50, 60)
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT_BLUE, self.rect, width=1, border_radius=6)

        txt_img = font.render(self.text, True, TEXT_COLOR)
        txt_rect = txt_img.get_rect(center=self.rect.center)
        screen.blit(txt_img, txt_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return self.callback_data
        return None


class AdvancedRoboldoGUI:
    def __init__(self):
        pygame.init()
        self.width, self.height = 1000, 650
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Roboldo - Painel de Controle Avançado")
        self.font = pygame.font.SysFont("Arial", 16)
        self.font_bold = pygame.font.SysFont("Arial", 18, bold=True)

        self.arm_len = 95
        self.forearm_len = 85
        self.body_pos = (700, 320)
        self.l_sh_base = (self.body_pos[0] - 60, self.body_pos[1] - 80)
        self.r_sh_base = (self.body_pos[0] + 60, self.body_pos[1] - 80)

        self.joints = {"l_sh_y": 0, "l_sh_x": 0, "l_el_x": 0, "r_sh_y": 0, "r_sh_x": 0, "r_el_x": 0}
        self.coords = {}

        self.current_anim = None
        self.animation_sequence = []
        self.status_message = "Sistema pronto"
        self.bluetooth = BluetoothSerialManager()
        self.buffer_playback_index = 0
        self.buffer_playback_timer = 0.0

        px, pw = 40, 260
        ys = [60, 110, 160, 220, 270, 320]
        self.sliders = {
            "l_sh_y": Slider(px, ys[0], pw, 0, 180, self.joints["l_sh_y"], "Ombro Esq - Yaw (Elevação)"),
            "l_sh_x": Slider(px, ys[1], pw, 0, 90, self.joints["l_sh_x"], "Ombro Esq - Pitch (Frente)"),
            "l_el_x": Slider(px, ys[2], pw, 0, 130, self.joints["l_el_x"], "Cotovelo Esq - Flexão"),
            "r_sh_y": Slider(px, ys[3], pw, 0, 180, self.joints["r_sh_y"], "Ombro Dir - Yaw (Elevação)"),
            "r_sh_x": Slider(px, ys[4], pw, 0, 90, self.joints["r_sh_x"], "Ombro Dir - Pitch (Frente)"),
            "r_el_x": Slider(px, ys[5], pw, 0, 130, self.joints["r_el_x"], "Cotovelo Dir - Flexão")
        }

        self.buttons = []
        for i, key in enumerate(self.sliders.keys()):
            self.buttons.append(Button(px + pw + 10, ys[i] - 5, 25, 22, "-", (key, -5)))
            self.buttons.append(Button(px + pw + 40, ys[i] - 5, 25, 22, "+", (key, 5)))

        self.buttons.append(Button(40, 400, 90, 30, "Tchau", "anim_wave"))
        self.buttons.append(Button(140, 400, 90, 30, "Marcha", "anim_march"))
        self.buttons.append(Button(240, 400, 95, 30, "Festa", "anim_cheer"))
        self.play_toggle_button = Button(40, 440, 295, 30, "Iniciar Buffer", "toggle_animation")
        self.send_esp32_button = Button(40, 480, 140, 30, "Enviar ESP32", "send_esp32")
        self.bluetooth_button = Button(195, 480, 140, 30, "Conectar ESP32", "connect_bluetooth")
        self.buttons.extend([self.play_toggle_button, self.send_esp32_button, self.bluetooth_button])

        self.buttons.append(Button(40, 525, 140, 35, "Salvar Keyframe", "save"))
        self.buttons.append(Button(195, 525, 140, 35, "Exportar Tokens", "export"))
        self.buttons.append(Button(40, 570, 295, 35, "Resetar Posição Inicial", "reset"))

    def update_button_texts(self):
        if self.current_anim:
            self.play_toggle_button.text = "Parar Animação"
        elif self.animation_sequence:
            self.play_toggle_button.text = "Iniciar Buffer"
        else:
            self.play_toggle_button.text = "Sem Buffer"

        self.bluetooth_button.text = "Desconectar ESP32" if self.bluetooth.connected else "Conectar ESP32"

    def apply_joint_snapshot(self, payload):
        for key in self.joints:
            if key in payload:
                self.joints[key] = int(payload[key])
        for key in self.joints:
            self.sliders[key].val = self.joints[key]
            self.sliders[key].update_knob_pos()

    def start_buffer_playback(self):
        if not self.animation_sequence:
            self.status_message = "Buffer vazio. Grave um keyframe primeiro."
            return

        self.current_anim = "buffer"
        self.buffer_playback_index = 0
        self.buffer_playback_timer = time.time()
        self.buffer_playback_start_time = time.time()
        self.buffer_transition_duration = 0.35
        self.apply_joint_snapshot(self.animation_sequence[0])
        self.status_message = "Executando sequência salva no buffer"

    def stop_current_animation(self):
        self.current_anim = None
        self.buffer_playback_index = 0
        self.status_message = "Animação interrompida"

    @staticmethod
    def gaussian_easing(t):
        """Animação suave usando curva gaussiana/smooth easing
        t: valor entre 0 e 1 representando progresso da transição
        """
        # Usa uma curva de easing smooth (ease-in-out cubic)
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - (-2 * t + 2) ** 3 / 2

    def interpolate_joint_states(self, state_a, state_b, progress):
        """Interpola suavemente entre dois estados de joint usando curva gaussiana"""
        eased_progress = self.gaussian_easing(progress)
        interpolated = {}
        for key in state_a:
            interpolated[key] = state_a[key] + (state_b[key] - state_a[key]) * eased_progress
        return interpolated

    def send_joint_state_to_esp32(self):
        if not self.bluetooth.connected:
            return
        self.bluetooth.send_payload(self.joints)

    def draw_status_panel(self):
        panel = pygame.Rect(380, 20, 600, 110)
        pygame.draw.rect(self.screen, (27, 31, 40), panel, border_radius=10)
        pygame.draw.rect(self.screen, ACCENT_BLUE, panel, width=1, border_radius=10)

        status_color = SUCCESS_GREEN if self.bluetooth.connected else DANGER_RED
        pygame.draw.circle(self.screen, status_color, (430, 62), 7)

        label = self.font_bold.render("ESP32", True, TEXT_COLOR)
        self.screen.blit(label, (445, 54))

        port_text = self.bluetooth.port if self.bluetooth.port else "desconectado"
        state_text = self.font.render(f"Status: {'conectado' if self.bluetooth.connected else 'offline'} | Porta: {port_text}", True, TEXT_COLOR)
        self.screen.blit(state_text, (430, 75))

        status_msg = self.font.render(self.status_message, True, TEXT_MUTED)
        self.screen.blit(status_msg, (430, 95))

    def process_animations(self):
        if self.current_anim == "buffer":
            if not self.animation_sequence:
                self.current_anim = None
                self.status_message = "Buffer vazio"
                return

            now = time.time()
            elapsed = now - self.buffer_playback_start_time
            frame_time = elapsed / self.buffer_transition_duration
            
            # Determina qual keyframe estamos buscando
            current_frame_index = int(frame_time)
            
            # Se chegamos ao fim
            if current_frame_index >= len(self.animation_sequence):
                self.current_anim = None
                self.status_message = "Buffer concluído"
                return
            
            # Progresso dentro do frame (0 a 1)
            frame_progress = frame_time - current_frame_index
            
            # Se é o primeiro keyframe, aplica diretamente
            if current_frame_index == 0:
                state_a = self.animation_sequence[0]
                if frame_progress < 1.0 and len(self.animation_sequence) > 1:
                    state_b = self.animation_sequence[1]
                    interpolated = self.interpolate_joint_states(state_a, state_b, frame_progress)
                    for key in self.joints:
                        self.joints[key] = int(interpolated[key])
                else:
                    self.apply_joint_snapshot(state_a)
            else:
                # Interpola entre frame anterior e atual
                state_a = self.animation_sequence[current_frame_index - 1]
                state_b = self.animation_sequence[current_frame_index]
                interpolated = self.interpolate_joint_states(state_a, state_b, frame_progress)
                for key in self.joints:
                    self.joints[key] = int(interpolated[key])
            
            self.buffer_playback_index = current_frame_index
            return

        if not self.current_anim:
            return

        t = pygame.time.get_ticks() / 1000.0

        if self.current_anim == "anim_wave":
            self.joints["r_sh_y"] = 160
            self.joints["r_sh_x"] = 0
            self.joints["r_el_x"] = 60 + int(45 * math.sin(t * 10))
            self.joints["l_sh_y"] = 10
            self.joints["l_sh_x"] = 0
            self.joints["l_el_x"] = 0

        elif self.current_anim == "anim_march":
            self.joints["l_sh_y"] = 10
            self.joints["r_sh_y"] = 10
            self.joints["l_sh_x"] = 45 + int(45 * math.sin(t * 6))
            self.joints["r_sh_x"] = 45 + int(45 * math.sin(t * 6 + math.pi))
            self.joints["l_el_x"] = 40
            self.joints["r_el_x"] = 40

        elif self.current_anim == "anim_cheer":
            self.joints["l_sh_y"] = 150 + int(30 * math.sin(t * 8))
            self.joints["r_sh_y"] = 150 + int(30 * math.sin(t * 8))
            self.joints["l_sh_x"] = 0
            self.joints["r_sh_x"] = 0
            self.joints["l_el_x"] = 30
            self.joints["r_el_x"] = 30

        for k in self.joints:
            self.sliders[k].val = self.joints[k]
            self.sliders[k].update_knob_pos()

    def update_kinematics(self):
        def get_arm_points(base_pos, sh_y, sh_x, el_x, is_left):
            dir_x = -1 if is_left else 1

            rad_y = math.radians(90 - sh_y)
            rad_x = math.radians(sh_x)
            rad_el = math.radians(el_x)

            el_x_coord = base_pos[0] + self.arm_len * math.cos(rad_y) * math.cos(rad_x) * dir_x
            el_y_coord = base_pos[1] + self.arm_len * math.sin(rad_y)
            el_z = self.arm_len * math.sin(rad_x)

            hand_rad = rad_y - rad_el
            h_x_coord = el_x_coord + self.forearm_len * math.cos(hand_rad) * math.cos(rad_x) * dir_x
            h_y_coord = el_y_coord + self.forearm_len * math.sin(hand_rad)
            h_z = el_z + self.forearm_len * math.sin(rad_x)

            return (base_pos, (int(el_x_coord), int(el_y_coord), el_z), (int(h_x_coord), int(h_y_coord), h_z))

        self.coords["left"] = get_arm_points(self.l_sh_base, self.joints["l_sh_y"], self.joints["l_sh_x"], self.joints["l_el_x"], True)
        self.coords["right"] = get_arm_points(self.r_sh_base, self.joints["r_sh_y"], self.joints["r_sh_x"], self.joints["r_el_x"], False)

    def draw_viewport(self):
        viewport_rect = pygame.Rect(380, 140, 600, 490)
        pygame.draw.rect(self.screen, (30, 34, 42), viewport_rect, border_radius=8)

        for x in range(380, 980, 40):
            pygame.draw.line(self.screen, (38, 42, 52), (x, 140), (x, 630))
        for y in range(140, 630, 40):
            pygame.draw.line(self.screen, (38, 42, 52), (380, y), (980, y))

        body_size = 100
        body_rect = pygame.Rect(self.body_pos[0] - body_size // 2, self.body_pos[1] - body_size // 2, body_size, body_size)
        pygame.draw.rect(self.screen, (68, 78, 96), body_rect, border_radius=14)

        for side in ["left", "right"]:
            pts = self.coords[side]
            sh, el, hd = pts[0], pts[1], pts[2]

            w_arm = max(8, int(16 + el[2] / 20))
            w_f_arm = max(6, int(12 + hd[2] / 20))

            pygame.draw.line(self.screen, (80, 86, 98), sh, (el[0], el[1]), w_arm)
            pygame.draw.line(self.screen, (105, 112, 125), (el[0], el[1]), (hd[0], hd[1]), w_f_arm)

            pygame.draw.circle(self.screen, JOINT_RED, sh, 12)
            pygame.draw.circle(self.screen, JOINT_GREEN, (el[0], el[1]), max(6, int(10 + el[2] / 20)))
            pygame.draw.circle(self.screen, ACCENT_BLUE, (hd[0], hd[1]), max(6, int(9 + hd[2] / 20)))

    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            self.screen.fill(BG_COLOR)
            self.update_button_texts()
            self.process_animations()
            self.update_kinematics()
            # Envio contínuo removido - use o botão "Enviar ESP32" para enviar dados manualmente
            # ou deixe conectado para sincronização automática

            if self.bluetooth.connected and self.bluetooth.connection:
                while self.bluetooth.connection.in_waiting > 0:
                    try:
                        linha = self.bluetooth.connection.readline().decode('utf-8').strip()
                        if linha:
                            print(f"[ESP32] {linha}")
                    except:
                        pass
                    
            pygame.draw.rect(self.screen, PANEL_COLOR, (15, 20, 350, 610), border_radius=8)
            title = self.font_bold.render("ROBOLDO - CONTROL PANEL", True, ACCENT_BLUE)
            self.screen.blit(title, (30, 35))

            pygame.draw.line(self.screen, (50, 54, 66), (30, 200), (350, 200), 2)
            pygame.draw.line(self.screen, (50, 54, 66), (30, 360), (350, 360), 2)

            anim_title = self.font_bold.render("PRESETS DE ANIMAÇÃO", True, ACCENT_HOVER)
            self.screen.blit(anim_title, (40, 375))
            pygame.draw.line(self.screen, (50, 54, 66), (30, 510), (350, 510), 2)

            for s in self.sliders.values():
                s.draw(self.screen, self.font)
            for b in self.buttons:
                b.draw(self.screen, self.font)

            self.draw_status_panel()
            self.draw_viewport()

            seq_txt = self.font.render(f"Buffer de Frames Gravados: {len(self.animation_sequence)}", True, TEXT_MUTED)
            self.screen.blit(seq_txt, (400, 600))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                for k, slider in self.sliders.items():
                    if slider.handle_event(event):
                        self.current_anim = None
                        self.joints[k] = int(slider.val)
                        self.send_joint_state_to_esp32()

                for button in self.buttons:
                    res = button.handle_event(event)
                    if not res:
                        continue

                    if res == "toggle_animation":
                        if self.current_anim:
                            self.stop_current_animation()
                        elif self.animation_sequence:
                            self.start_buffer_playback()
                        else:
                            self.status_message = "Buffer vazio. Grave um keyframe primeiro."

                    elif res == "connect_bluetooth":
                        if self.bluetooth.connected:
                            self.bluetooth.disconnect()
                            self.status_message = "Conexão com ESP32 encerrada"
                        else:
                            if self.bluetooth.connect():
                                self.status_message = f"ESP32 conectado em {self.bluetooth.port}"
                            else:
                                self.status_message = self.bluetooth.last_error or "Não foi possível conectar ao ESP32"

                    elif res == "send_esp32":
                        if self.bluetooth.connected:
                            self.send_joint_state_to_esp32()
                            self.status_message = f"Dados enviados para ESP32 em {self.bluetooth.port}"
                        else:
                            self.status_message = "ESP32 não conectado. Clique em 'Conectar ESP32' primeiro."

                    elif str(res).startswith("anim_"):
                        if res == "anim_stop":
                            self.stop_current_animation()
                        else:
                            self.current_anim = res
                            self.status_message = f"Animação ativa: {res}"

                    elif isinstance(res, tuple):
                        self.current_anim = None
                        k, amt = res
                        self.sliders[k].val = max(self.sliders[k].min_val, min(self.sliders[k].max_val, self.sliders[k].val + amt))
                        self.sliders[k].update_knob_pos()
                        self.joints[k] = int(self.sliders[k].val)
                        self.status_message = f"Joint {k} ajustado manualmente"
                        self.send_joint_state_to_esp32()

                    elif res == "save":
                        self.animation_sequence.append(self.joints.copy())
                        self.status_message = f"Keyframe salvo no buffer ({len(self.animation_sequence)})"
                        print(f"Keyframe adicionado no buffer! ({len(self.animation_sequence)} no total)")

                    elif res == "export":
                        print("\n=== LISTA DE TOKENS EXPORTADA ===")
                        print(json.dumps(self.animation_sequence, indent=2))
                        self.animation_sequence.clear()
                        self.status_message = "Tokens exportados e buffer limpo"

                    elif res == "reset":
                        self.current_anim = None
                        self.joints = {k: 0 for k in self.joints}
                        for k in self.joints:
                            self.sliders[k].val = 0
                            self.sliders[k].update_knob_pos()
                        self.status_message = "Posição inicial restaurada"
                        self.send_joint_state_to_esp32()

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    app = AdvancedRoboldoGUI()
    app.run()