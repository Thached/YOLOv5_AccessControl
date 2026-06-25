#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <stdbool.h>
#include "src/SensorControl.h"
int main()
{    
    Sensor_init();    
    while(1)    
    {           
        int sw = 0;        
        scanf("%d",&sw);        
        Sensor_Control(sw);    
    }
}