#ifndef _SERVO_H
#define _SERVO_H
void SERVO_init(void);void FS90_Set_PWM(unsigned short brightpercent);void Set_SERVO_OPEN();void Set_SERVO_CLOSE();
#define WR_8BIT_CMD            0x03
#define WR_16BIT_CMD           0X02
#define GP7101_ADDRESS         0x58
#define GP7101_BAUDRATE        1000000
#define I2C 0
#define GPIO7_LED_GRN 7
#define GPIO60_LED_GRN 60
#define GPIO9_BUZ1 9
#endif // _SERVO_H