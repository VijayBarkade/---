# 𝗩𝗼𝗶𝗰𝗲-𝗖𝗼𝗻𝘁𝗿𝗼𝗹𝗹𝗲𝗱 𝗟𝗘𝗗 𝗠𝗮𝘁𝗿𝗶𝘅 𝗗𝗶𝘀𝗽𝗹𝗮𝘆 𝘂𝘀𝗶𝗻𝗴 𝗔𝗿𝗱𝘂𝗶𝗻𝗼 𝗨𝗻𝗼 𝗤

App Lab project for Arduino Uno Q that listens to your words in the browser, previews them on the Arduino Uno Q built-in 8 x 13 LED matrix, and sends the same words to the STM32 MCU through Bridge.

The Arduino Uno Q built-in matrix is not a 32 x 8 MAX7219 module. It is an onboard 8 x 13 monochrome blue LED matrix, driven by the STM32 microcontroller.

## Run In Arduino App Lab

Open this folder in Arduino App Lab and press **Run**.

Then open:

```text
http://<UNO_Q_IP>:5002
```

For microphone access from Chrome on Windows, tunnel the port:

```bash
ssh -N -L 5002:127.0.0.1:5002 arduino@<UNO_Q_IP>
```

Then open:

```text
http://127.0.0.1:5002
```

## How It Talks To The Matrix

The Python app calls this Bridge RPC function on the MCU:

```text
display_text("HELLO")
set_scroll("1")
set_speed("150")
```

The sketch receives the text, scroll on/off state, and scroll speed, then updates the built-in 13 x 8 matrix. No external LED module or wiring is needed.

## Files

- `python/main.py`: browser UI and speech/text input.
- `sketch/sketch.ino`: MCU sketch for the built-in Arduino Uno Q matrix.

## Required Sketch Libraries

In Arduino App Lab, add these sketch libraries if they are not already available:

- `Arduino_LED_Matrix`
- `Arduino_RouterBridge`
