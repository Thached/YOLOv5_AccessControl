#include "servo.h"
#include "../gpio.h"
#include <stdio.h>
#include "../i2c/smbus.h"
#include "../i2c/i2cbusses.h"
#include <unistd.h>

/****************************************************************************************
** 函数功能：初始化GP7101
** 参数：无
** 说明：
***************************************************************************************/

void SERVO_init(void)
{
    gpio_init();
    gpio_enable(GPIO7_LED_GRN, 1);
    gpio_enable(GPIO60_LED_GRN, 1);
    gpio_enable(GPIO9_BUZ1, 1);
    char filename[20];
    //打开I2C
    file = open_i2c_dev(I2C, filename, sizeof(filename), 0);
    usleep(10);
    //设置器件地址
    set_slave_addr(file, GP7101_ADDRESS, 1);
    usleep(10);
    Set_SERVO_CLOSE();
}

//脉冲宽度范围500~1500~2500us -- 0.5~1.5~2.5ms -->1638~8192 -->16位//8350 -- 4720 -- 1680
/***************************************************************************************
** 函数功能：控制舵机的偏转角度
** 参数：unsigned char brightpercent：填入的数值为：0 ~ 120
** 说明：周期20ms          FS90偏转角度0~120度          脉冲宽度范围900~1500~2100us -- 0.9~2.1ms -->2949~6881 -->16位
**      0刻度的数值--6650
**      90刻度的数值--4915
**      120刻度的数值--2940
***************************************************************************************/
void FS90_Set_PWM(unsigned short brightpercent)
{
    unsigned char data[3] = {0};
    unsigned short brightness = brightpercent;

    if (brightpercent >= 140)
    {
        brightness = 2880-(brightpercent-140) * 30;
        //每减30，指针偏转一度
    }
    else
    {
        brightness = 8350-brightpercent*40;
        //每减40，指针偏转一度
    }

    set_slave_addr(file, GP7101_ADDRESS, 1);
    usleep(100);
    //16位PWM模式
    data[0] = WR_16BIT_CMD;
    //数据
    data[1] = brightness;
    data[2] = brightness >> 8;
    short DATA = data[1] | (data[2] << 8);
    i2c_smbus_write_word_data(file, 0x02, brightness);
}

void Set_SERVO_OPEN()
{
    FS90_Set_PWM(90);
    gpio_write(GPIO7_LED_GRN, 0);
    gpio_write(GPIO60_LED_GRN, 1);
    gpio_write(GPIO9_BUZ1,1);
}

void Set_SERVO_CLOSE()
{
    FS90_Set_PWM(0);
    gpio_write(GPIO7_LED_GRN, 1);
    gpio_write(GPIO60_LED_GRN, 0);
    gpio_write(GPIO9_BUZ1,0);
}