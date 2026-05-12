import config

try:
    import machine
except Exception:
    machine = None

try:
    from time import ticks_diff, sleep_ms
except Exception:
    from time import sleep as _sleep

    def ticks_diff(a, b):
        return a - b

    def sleep_ms(ms):
        _sleep(ms / 1000)


class InputSystem:
    __slots__ = (
        "joy_x_axis",
        "joy_y_axis",
        "btn_a_down",
        "btn_b_down",
        "btn_x_down",
        "btn_y_down",
        "btn_a_pressed",
        "btn_b_pressed",
        "btn_x_pressed",
        "btn_y_pressed",
        "system_quit_requested",
        "_adc_x",
        "_adc_y",
        "_btn_pins",
        "_btn_raw",
        "_btn_stable",
        "_btn_last_change",
        "_center_x",
        "_center_y",
        "_raw_min",
        "_raw_max",
        "_snap_to_zero",
        "_saturate_threshold",
        "_smooth_num",
        "_smooth_den",
    )

    def __init__(self):
        self.joy_x_axis = 0
        self.joy_y_axis = 0

        self.btn_a_down = False
        self.btn_b_down = False
        self.btn_x_down = False
        self.btn_y_down = False

        self.btn_a_pressed = False
        self.btn_b_pressed = False
        self.btn_x_pressed = False
        self.btn_y_pressed = False

        self.system_quit_requested = False

        self._adc_x = None
        self._adc_y = None
        self._btn_pins = [None, None, None, None]
        self._btn_raw = [0, 0, 0, 0]
        self._btn_stable = [0, 0, 0, 0]
        self._btn_last_change = [0, 0, 0, 0]

        self._center_x = 32768
        self._center_y = 32768
        self._raw_min = int(getattr(config, "JOY_AXIS_RAW_MIN", 0))
        self._raw_max = int(getattr(config, "JOY_AXIS_RAW_MAX", 65535))
        if self._raw_max <= self._raw_min:
            self._raw_min = 0
            self._raw_max = 65535

        self._snap_to_zero = int(getattr(config, "JOY_SNAP_TO_ZERO", 3))
        if self._snap_to_zero < 0:
            self._snap_to_zero = 0

        self._saturate_threshold = int(getattr(config, "JOY_SATURATE_THRESHOLD", 96))
        if self._saturate_threshold < 1:
            self._saturate_threshold = 1
        elif self._saturate_threshold > 100:
            self._saturate_threshold = 100

        self._smooth_den = int(getattr(config, "JOY_SMOOTH_DEN", 4))
        if self._smooth_den < 2:
            self._smooth_den = 2
        self._smooth_num = int(getattr(config, "JOY_SMOOTH_NUM", self._smooth_den - 1))
        if self._smooth_num < 0 or self._smooth_num >= self._smooth_den:
            self._smooth_num = self._smooth_den - 1

        if machine is None:
            return

        try:
            self._adc_x = machine.ADC(machine.Pin(config.JOY_X_PIN))
            self._adc_y = machine.ADC(machine.Pin(config.JOY_Y_PIN))
            if hasattr(machine.ADC, "ATTN_11DB"):
                self._adc_x.atten(machine.ADC.ATTN_11DB)
                self._adc_y.atten(machine.ADC.ATTN_11DB)
        except Exception:
            self._adc_x = None
            self._adc_y = None

        pin_ids = [config.BTN_A_PIN, config.BTN_B_PIN, config.BTN_X_PIN, config.BTN_Y_PIN]
        for i in range(4):
            try:
                self._btn_pins[i] = machine.Pin(pin_ids[i], machine.Pin.IN, machine.Pin.PULL_UP)
            except Exception:
                self._btn_pins[i] = None

        self._calibrate_joy_center()

    def _clamp(self, v, lo, hi):
        if v < lo:
            return lo
        if v > hi:
            return hi
        return v

    def _calibrate_joy_center(self):
        if self._adc_x is None or self._adc_y is None:
            return

        samples = int(getattr(config, "JOY_CALIB_SAMPLES", 32))
        delay_ms = int(getattr(config, "JOY_CALIB_INTERVAL_MS", 2))

        if samples < 4:
            samples = 4
        if delay_ms < 0:
            delay_ms = 0

        sum_x = 0
        sum_y = 0
        i = 0
        while i < samples:
            sum_x += self._read_adc_u16(self._adc_x)
            sum_y += self._read_adc_u16(self._adc_y)
            if delay_ms > 0:
                sleep_ms(delay_ms)
            i += 1

        center_x = sum_x // samples
        center_y = sum_y // samples

        # Keep center away from boundaries to avoid tiny normalization spans.
        guard = 1024
        low = self._raw_min + guard
        high = self._raw_max - guard
        if low >= high:
            low = self._raw_min
            high = self._raw_max

        self._center_x = self._clamp(center_x, low, high)
        self._center_y = self._clamp(center_y, low, high)

    def get_joy_centers(self):
        return self._center_x, self._center_y

    def set_joy_centers(self, center_x, center_y):
        guard = 1024
        low = self._raw_min + guard
        high = self._raw_max - guard
        if low >= high:
            low = self._raw_min
            high = self._raw_max
        self._center_x = self._clamp(int(center_x), low, high)
        self._center_y = self._clamp(int(center_y), low, high)

    def _read_adc_u16(self, adc_obj):
        if adc_obj is None:
            return 32768
        if hasattr(adc_obj, "read_u16"):
            return adc_obj.read_u16()
        if hasattr(adc_obj, "read"):
            return adc_obj.read() << 4
        return 32768

    def _normalize_axis(self, raw, old, center):
        delta = int(raw) - center
        if -config.JOY_DEAD_ZONE < delta < config.JOY_DEAD_ZONE:
            target = 0
        else:
            if delta >= 0:
                span = self._raw_max - center
                if span < 1:
                    span = 1
                target = (delta * 100 + (span // 2)) // span
            else:
                span = center - self._raw_min
                if span < 1:
                    span = 1
                target = -(((-delta) * 100 + (span // 2)) // span)

            if target > 100:
                target = 100
            elif target < -100:
                target = -100

            sat = self._saturate_threshold
            if target >= sat:
                target = 100
            elif target <= -sat:
                target = -100

        mix = old * self._smooth_num + target
        half = self._smooth_den // 2
        if mix >= 0:
            filtered = (mix + half) // self._smooth_den
        else:
            filtered = -(((-mix) + half) // self._smooth_den)

        snap = self._snap_to_zero
        if -snap <= filtered <= snap:
            return 0
        return filtered

    def _apply_button_sample(self, i, pressed, now_ms, debounce):
        if pressed != self._btn_raw[i]:
            self._btn_raw[i] = pressed
            self._btn_last_change[i] = now_ms

        if ticks_diff(now_ms, self._btn_last_change[i]) < debounce:
            return False

        if self._btn_stable[i] == self._btn_raw[i]:
            return False

        prev = self._btn_stable[i]
        self._btn_stable[i] = self._btn_raw[i]
        return prev == 0 and self._btn_stable[i] == 1

    def update_from_raw(self, raw_x, raw_y, btn_a, btn_b, btn_x, btn_y, now_ms):
        self.btn_a_pressed = False
        self.btn_b_pressed = False
        self.btn_x_pressed = False
        self.btn_y_pressed = False

        self.joy_x_axis = self._normalize_axis(raw_x, self.joy_x_axis, self._center_x)
        self.joy_y_axis = self._normalize_axis(raw_y, self.joy_y_axis, self._center_y)

        debounce = config.INPUT_DEBOUNCE_MS
        btn_vals = (
            1 if btn_a else 0,
            1 if btn_b else 0,
            1 if btn_x else 0,
            1 if btn_y else 0,
        )

        i = 0
        while i < 4:
            if self._apply_button_sample(i, btn_vals[i], now_ms, debounce):
                if i == 0:
                    self.btn_a_pressed = True
                elif i == 1:
                    self.btn_b_pressed = True
                elif i == 2:
                    self.btn_x_pressed = True
                else:
                    self.btn_y_pressed = True
            i += 1

        self.btn_a_down = self._btn_stable[0] == 1
        self.btn_b_down = self._btn_stable[1] == 1
        self.btn_x_down = self._btn_stable[2] == 1
        self.btn_y_down = self._btn_stable[3] == 1

    def update(self, now_ms):
        raw_x = self._read_adc_u16(self._adc_x)
        raw_y = self._read_adc_u16(self._adc_y)
        btn_a = False
        btn_b = False
        btn_x = False
        btn_y = False

        pin = self._btn_pins[0]
        if pin is not None:
            btn_a = pin.value() == 0
        pin = self._btn_pins[1]
        if pin is not None:
            btn_b = pin.value() == 0
        pin = self._btn_pins[2]
        if pin is not None:
            btn_x = pin.value() == 0
        pin = self._btn_pins[3]
        if pin is not None:
            btn_y = pin.value() == 0

        self.update_from_raw(raw_x, raw_y, btn_a, btn_b, btn_x, btn_y, now_ms)
