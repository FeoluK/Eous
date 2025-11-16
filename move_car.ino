// Four-wheel robot control via serial commands from Raspberry Pi, using the
// same motor pins and TB6612 driver wiring as the Elegoo Smart Robot Car V4.0.
//
// Commands (single ASCII characters sent over USB serial):
//   'W' - move forward for 1 second
//   'S' - move backward for 1 second
//   'A' - rotate left (on the spot) for 1 second
//   'D' - rotate right (on the spot) for 1 second
//   'X' - stop immediately
//
// NOTE ABOUT HARDWARE:
// The Elegoo Smart Robot Car V4.0 drives all right-side motors together and
// all left-side motors together via a TB6612 dual‑H‑bridge driver.
// The official firmware uses the following Arduino pins:
//   - PIN_Motor_PWMA : D5  (right side PWM/speed)
//   - PIN_Motor_PWMB : D6  (left  side PWM/speed)
//   - PIN_Motor_AIN_1: D7  (right side direction)
//   - PIN_Motor_BIN_1: D8  (left  side direction)
//   - PIN_Motor_STBY : D3  (driver standby/enable)
//
// This sketch reuses exactly those pins so it is plug‑compatible with the
// stock SmartRobotCarV4.0 wiring.

// Match SmartRobotCarV4.0 motor pins
const int RIGHT_PWM  = 5;  // PIN_Motor_PWMA
const int LEFT_PWM   = 6;  // PIN_Motor_PWMB
const int RIGHT_DIR  = 7;  // PIN_Motor_AIN_1 (right side direction)
const int LEFT_DIR   = 8;  // PIN_Motor_BIN_1 (left side direction)
const int MOTOR_STBY = 3;  // PIN_Motor_STBY  (standby / enable)

// Run motors at ~1/3 of full speed (3x slower than full power)
const int TURN_MOTOR_SPEED = 255;  // PWM value in [0,255]
const int FB_MOTOR_SPEED = 150;  // PWM value in [0,255]

// Direction helpers for the right side
void rightForward(int motor_speed) {
  digitalWrite(MOTOR_STBY, HIGH);   // enable driver
  digitalWrite(RIGHT_DIR, HIGH);    // HIGH = forward (matches stock firmware)
  analogWrite(RIGHT_PWM, motor_speed);
}

void rightBackward(int motor_speed) {
  digitalWrite(MOTOR_STBY, HIGH);
  digitalWrite(RIGHT_DIR, LOW);     // LOW = backward
  analogWrite(RIGHT_PWM, motor_speed);
}

void rightStop() {
  analogWrite(RIGHT_PWM, 0);
  digitalWrite(MOTOR_STBY, LOW);
}

// Direction helpers for the left side
void leftForward(int motor_speed) {
  digitalWrite(MOTOR_STBY, HIGH);
  digitalWrite(LEFT_DIR, HIGH);     // HIGH = forward
  analogWrite(LEFT_PWM, motor_speed);
}

void leftBackward(int motor_speed) {
  digitalWrite(MOTOR_STBY, HIGH);
  digitalWrite(LEFT_DIR, LOW);      // LOW = backward
  analogWrite(LEFT_PWM, motor_speed);
}

void leftStop() {
  analogWrite(LEFT_PWM, 0);
  digitalWrite(MOTOR_STBY, LOW);
}

// Stop both sides
void stopAllMotors() {
  rightStop();
  leftStop();
}

// Move forward (both sides forward)
void allForward() {
  rightForward(FB_MOTOR_SPEED);
  leftForward(FB_MOTOR_SPEED);
}

// Move backward (both sides backward)
void allBackward() {
  rightBackward(FB_MOTOR_SPEED);
  leftBackward(FB_MOTOR_SPEED);
}

// Rotate left: left side backward, right side forward
void rotateLeft() {
  leftBackward(TURN_MOTOR_SPEED);
  rightForward(TURN_MOTOR_SPEED);
}

// Rotate right: left side forward, right side backward
void rotateRight() {
  leftForward(TURN_MOTOR_SPEED);
  rightBackward(TURN_MOTOR_SPEED);
}

void setup() {
  // Initialize serial communication with the Raspberry Pi
  Serial.begin(9600);

  // Configure motor pins as outputs (matching SmartRobotCarV4.0)
  pinMode(RIGHT_PWM, OUTPUT);
  pinMode(LEFT_PWM, OUTPUT);
  pinMode(RIGHT_DIR, OUTPUT);
  pinMode(LEFT_DIR, OUTPUT);
  pinMode(MOTOR_STBY, OUTPUT);

  // Ensure motors are stopped at startup
  stopAllMotors();
}

void loop() {
  // Check if a command has arrived from the Raspberry Pi
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    switch (cmd) {
      case 'W':
      case 'w':
        allForward();       // drive forward until another command (or 'X') is received
        break;
      case 'S':
      case 's':
        allBackward();      // drive backward until another command (or 'X') is received
        break;
      case 'A':
      case 'a':
        rotateLeft();       // rotate left until another command (or 'X') is received
        break;
      case 'D':
      case 'd':
        rotateRight();      // rotate right until another command (or 'X') is received
        break;
      case 'X':
      case 'x':
        stopAllMotors();
        break;
      default:
        // Ignore any unknown characters (including newlines, etc.)
        break;
    }
  }
}