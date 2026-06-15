#include "Arduino_LED_Matrix.h"
#include "Arduino_RouterBridge.h"

const uint8_t MATRIX_COLS = 13;
const uint8_t MATRIX_ROWS = 8;
const uint8_t GLYPH_WIDTH = 5;
const uint8_t MAX_TEXT = 80;

ArduinoLEDMatrix matrix;
uint8_t frame[MATRIX_ROWS * MATRIX_COLS] = {0};
char message[MAX_TEXT + 1] = "HELLO ARDUINO";
int scrollColumn = -MATRIX_COLS;
unsigned long lastStepMs = 0;
unsigned long scrollDelayMs = 150;
bool scrollEnabled = true;

const uint8_t font[][7] = {
  {0b01110,0b10001,0b10011,0b10101,0b11001,0b10001,0b01110}, // 0
  {0b00100,0b01100,0b00100,0b00100,0b00100,0b00100,0b01110}, // 1
  {0b01110,0b10001,0b00001,0b00010,0b00100,0b01000,0b11111}, // 2
  {0b11110,0b00001,0b00001,0b01110,0b00001,0b00001,0b11110}, // 3
  {0b00010,0b00110,0b01010,0b10010,0b11111,0b00010,0b00010}, // 4
  {0b11111,0b10000,0b11110,0b00001,0b00001,0b10001,0b01110}, // 5
  {0b00110,0b01000,0b10000,0b11110,0b10001,0b10001,0b01110}, // 6
  {0b11111,0b00001,0b00010,0b00100,0b01000,0b01000,0b01000}, // 7
  {0b01110,0b10001,0b10001,0b01110,0b10001,0b10001,0b01110}, // 8
  {0b01110,0b10001,0b10001,0b01111,0b00001,0b00010,0b11100}, // 9
  {0b01110,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}, // A
  {0b11110,0b10001,0b10001,0b11110,0b10001,0b10001,0b11110}, // B
  {0b01111,0b10000,0b10000,0b10000,0b10000,0b10000,0b01111}, // C
  {0b11110,0b10001,0b10001,0b10001,0b10001,0b10001,0b11110}, // D
  {0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b11111}, // E
  {0b11111,0b10000,0b10000,0b11110,0b10000,0b10000,0b10000}, // F
  {0b01111,0b10000,0b10000,0b10011,0b10001,0b10001,0b01111}, // G
  {0b10001,0b10001,0b10001,0b11111,0b10001,0b10001,0b10001}, // H
  {0b01110,0b00100,0b00100,0b00100,0b00100,0b00100,0b01110}, // I
  {0b00111,0b00010,0b00010,0b00010,0b00010,0b10010,0b01100}, // J
  {0b10001,0b10010,0b10100,0b11000,0b10100,0b10010,0b10001}, // K
  {0b10000,0b10000,0b10000,0b10000,0b10000,0b10000,0b11111}, // L
  {0b10001,0b11011,0b10101,0b10101,0b10001,0b10001,0b10001}, // M
  {0b10001,0b11001,0b10101,0b10011,0b10001,0b10001,0b10001}, // N
  {0b01110,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}, // O
  {0b11110,0b10001,0b10001,0b11110,0b10000,0b10000,0b10000}, // P
  {0b01110,0b10001,0b10001,0b10001,0b10101,0b10010,0b01101}, // Q
  {0b11110,0b10001,0b10001,0b11110,0b10100,0b10010,0b10001}, // R
  {0b01111,0b10000,0b10000,0b01110,0b00001,0b00001,0b11110}, // S
  {0b11111,0b00100,0b00100,0b00100,0b00100,0b00100,0b00100}, // T
  {0b10001,0b10001,0b10001,0b10001,0b10001,0b10001,0b01110}, // U
  {0b10001,0b10001,0b10001,0b10001,0b10001,0b01010,0b00100}, // V
  {0b10001,0b10001,0b10001,0b10101,0b10101,0b10101,0b01010}, // W
  {0b10001,0b10001,0b01010,0b00100,0b01010,0b10001,0b10001}, // X
  {0b10001,0b10001,0b01010,0b00100,0b00100,0b00100,0b00100}, // Y
  {0b11111,0b00001,0b00010,0b00100,0b01000,0b10000,0b11111}, // Z
};

int glyphIndex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'Z') return c - 'A' + 10;
  return -1;
}

int textWidth() {
  int len = strlen(message);
  if (len == 0) return MATRIX_COLS;
  return len * (GLYPH_WIDTH + 1);
}

void resetScrollPosition() {
  if (scrollEnabled) {
    scrollColumn = -MATRIX_COLS;
    return;
  }

  int width = textWidth();
  if (width <= MATRIX_COLS) {
    scrollColumn = -((MATRIX_COLS - width) / 2);
  } else {
    scrollColumn = 0;
  }
}

bool columnForText(int textCol, uint8_t row) {
  if (textCol < 0) return false;
  int charIndex = textCol / (GLYPH_WIDTH + 1);
  int localCol = textCol % (GLYPH_WIDTH + 1);
  if (localCol >= GLYPH_WIDTH || charIndex >= (int)strlen(message)) return false;
  int idx = glyphIndex(message[charIndex]);
  if (idx < 0) return false;
  if (row == 0) return false;
  return (font[idx][row - 1] >> (GLYPH_WIDTH - 1 - localCol)) & 1;
}

void renderFrame() {
  memset(frame, 0, sizeof(frame));
  for (uint8_t row = 0; row < MATRIX_ROWS; row++) {
    for (uint8_t col = 0; col < MATRIX_COLS; col++) {
      frame[row * MATRIX_COLS + col] = columnForText(scrollColumn + col, row) ? 1 : 0;
    }
  }
  matrix.draw(frame);
}

String display_text(String value) {
  value.trim();
  value.toUpperCase();
  if (value.length() == 0) {
    value = " ";
  }
  value.toCharArray(message, sizeof(message));
  resetScrollPosition();
  renderFrame();
  return "OK";
}

String set_scroll(String value) {
  value.trim();
  scrollEnabled = value == "1" || value == "true" || value == "TRUE" || value == "on" || value == "ON";
  resetScrollPosition();
  renderFrame();
  return scrollEnabled ? "SCROLL_ON" : "SCROLL_OFF";
}

String set_speed(String value) {
  value.trim();
  long nextDelay = value.toInt();
  if (nextDelay < 90) {
    nextDelay = 90;
  }
  if (nextDelay > 320) {
    nextDelay = 320;
  }
  scrollDelayMs = (unsigned long)nextDelay;
  return "SPEED_OK";
}

void setup() {
  Bridge.begin();
  Monitor.begin();
  Bridge.provide_safe("display_text", display_text);
  Bridge.provide_safe("set_scroll", set_scroll);
  Bridge.provide_safe("set_speed", set_speed);
  matrix.begin();
  matrix.setGrayscaleBits(1);
  display_text("HELLO ARDUINO");
  Monitor.println("Arduino Uno Q built-in LED matrix ready");
}

void loop() {
  if (!scrollEnabled) {
    return;
  }

  unsigned long now = millis();
  if (now - lastStepMs < scrollDelayMs) {
    return;
  }
  lastStepMs = now;
  scrollColumn++;
  if (scrollColumn > textWidth()) {
    scrollColumn = -MATRIX_COLS;
  }
  renderFrame();
}
