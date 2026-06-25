#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <stdbool.h>
#include "cs100a.h"
#include "servo.h"
#include "MLX90614.h"
#include "../i2c/smbus.h"
#include "../i2c/i2cbusses.h"
#include <unistd.h>

int Sensor_Control(int sw)
{
    int dist,to;
    if(sw == 1)
    {
        dist = CS100A_Get_Dist();
        return dist;
    }
    else if(sw == 2)
    {
        Set_SERVO_OPEN();
        return 2;
    }
    else if(sw == 3)
    {
        Set_SERVO_CLOSE();
        return 3;
    }
    else if(sw == 4)
    {
        to = MLX90614_GET();
        return to;
    }
}

void Sensor_init()
{
    SERVO_init();
    CS100A_IO_Config();
    MLX90614_init();
}