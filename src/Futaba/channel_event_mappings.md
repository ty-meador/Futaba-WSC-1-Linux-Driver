# Linux Input Event Codes

## Absolute Axis Events (EV_ABS - Type 3)

| Event Name | Code | Tuple | RC Use Case |
|------------|------|-------|-------------|
| ABS_X | 0 | (3, 0) | Primary stick X (aileron/roll) |
| ABS_Y | 1 | (3, 1) | Primary stick Y (elevator/pitch) |
| ABS_Z | 2 | (3, 2) | Altitude/collective (helicopters) |
| ABS_RX | 3 | (3, 3) | Secondary stick X (camera pan) |
| ABS_RY | 4 | (3, 4) | Secondary stick Y (camera tilt) |
| ABS_RZ | 5 | (3, 5) | Rotation/twist |
| ABS_THROTTLE | 6 | (3, 6) | Main throttle control |
| ABS_RUDDER | 7 | (3, 7) | Rudder/yaw control |
| ABS_WHEEL | 8 | (3, 8) | Wheel/steering |
| ABS_GAS | 9 | (3, 9) | Gas/acceleration |
| ABS_BRAKE | 10 | (3, 10) | Brake control |
| ABS_HAT0X | 16 | (3, 16) | D-pad/trim X |
| ABS_HAT0Y | 17 | (3, 17) | D-pad/trim Y |
| ABS_HAT1X | 18 | (3, 18) | Second D-pad X |
| ABS_HAT1Y | 19 | (3, 19) | Second D-pad Y |
| ABS_TILT_X | 26 | (3, 26) | Tilt sensor X |
| ABS_TILT_Y | 27 | (3, 27) | Tilt sensor Y |

## Button Events (EV_KEY - Type 1) - For Toggle/Button Channels

| Event Name | Code | Tuple | RC Use Case |
|------------|------|-------|-------------|
| BTN_TRIGGER | 256 | (1, 256) | Primary trigger button |
| BTN_THUMB | 257 | (1, 257) | Thumb button |
| BTN_THUMB2 | 258 | (1, 258) | Second thumb button |
| BTN_TOP | 259 | (1, 259) | Top button |
| BTN_TOP2 | 260 | (1, 260) | Second top button |
| BTN_PINKIE | 261 | (1, 261) | Pinkie button |
| BTN_BASE | 262 | (1, 262) | Base button |
| BTN_BASE2 | 263 | (1, 263) | Second base button |
| BTN_BASE3 | 264 | (1, 264) | Third base button |
| BTN_BASE4 | 265 | (1, 265) | Fourth base button |
| BTN_BASE5 | 266 | (1, 266) | Fifth base button |
| BTN_BASE6 | 267 | (1, 267) | Sixth base button |
| BTN_DEAD | 271 | (1, 271) | Dead man's switch |
| BTN_A | 304 | (1, 304) | Gamepad A button |
| BTN_B | 305 | (1, 305) | Gamepad B button |
| BTN_C | 306 | (1, 306) | Gamepad C button |
| BTN_X | 307 | (1, 307) | Gamepad X button |
| BTN_Y | 308 | (1, 308) | Gamepad Y button |
| BTN_Z | 309 | (1, 309) | Gamepad Z button |
| BTN_TL | 310 | (1, 310) | Top left shoulder |
| BTN_TR | 311 | (1, 311) | Top right shoulder |
| BTN_TL2 | 312 | (1, 312) | Second top left |
| BTN_TR2 | 313 | (1, 313) | Second top right |
