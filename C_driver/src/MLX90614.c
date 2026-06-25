#include <stdio.h>
#include "../i2c/smbus.h"
#include "../i2c/i2cbusses.h"
#include "../gpio.h"
#include "MLX90614.h"
#include <unistd.h>


//初始化
void MLX90614_init(void)
{
    char filename[20];
    int ID[4];
    //打开I2C
    file = open_i2c_dev(I2C, filename, sizeof(filename), 0);
    usleep(100);
}

int MLX90614_GET()
{
    float Ta_d;
    float To_d;
    float tbody = 0;
    int tbody_100 = 0;
    short To, Ta;
    char datal, datah;
    set_slave_addr(file, MLX90614_DEVICE_ADDR, 1);
    usleep(100);
    Ta = i2c_smbus_read_word_data(file, 0x06);
    usleep(100);
    To = i2c_smbus_read_word_data(file, 0x07);
    usleep(100);

    Ta_d = Ta * 0.02 - 273.15;
    To_d = To * 0.02 - 273.15;

    tbody = getTempbody(Ta_d ,To_d);
    tbody_100 = tbody*100;

    if (tbody_100 >= 0) {
        printf("体温: %.2f ℃\n", tbody_100 / 100.0);
    } else {
        printf("体温测量超时\n");
    }

    return tbody_100;
}

/*******************************************************************
**函数名：getTempbody
**函数功能：额温转体温算法
**形参：无
**返回值：计算的体温
**说明：
*******************************************************************/
float getTempbody(float ta,float tf)//迈来芯额温转体温算法
{
    //ta为芯片内部温度，tf为额温，tbody为体温
    float tbody = 0;
    float tf_low,tf_high = 0;
    float TA_LEVEL = 25;
    //判断界限，环境温度
    if(ta <= TA_LEVEL)//环境温度小于或等于25度
    {
        tf_low  = 32.66 + 0.186 * (ta - TA_LEVEL);
        tf_high = 34.84 + 0.148 * (ta - TA_LEVEL);
    }
    else//环境温度大于25度
    {
        tf_low  = 32.66 + 0.086 * (ta - TA_LEVEL);
        tf_high = 34.84 + 0.1 * (ta - TA_LEVEL);
    }
    //先是计算出tf_low和tf_high,再通过tf_low和tf_high计算出tbody
    if(tf_low <= tf && tf <= tf_high)
    {
        tbody = 36.3 + 0.5 / (tf_high - tf_low) * (tf - tf_low);
    }
    else if(tf > tf_high)//额温大于tf_high
    {
        tbody = 36.8 + (0.029321 + 0.002364 * ta) * (tf - tf_high);
    }
    else if(tf < tf_low)//额温小于tf_low
    {
        tbody = 36.3 + (0.551658 + 0.021525 * ta) * (tf - tf_low);
    }
    return tbody;//返回获得的体温
}