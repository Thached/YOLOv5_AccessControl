#include "cs100a.h"
#include "../gpio.h"
#include <sys/time.h>
#include <stdbool.h>
#include <stdio.h>
#include <unistd.h>

void CS100A_IO_Config(void){
    gpio_init();
    gpio_enable(TRIG, DIR_OUT);
    gpio_enable(ECHO, DIR_IN);
    gpio_write(TRIG, 0);
}

int CS100A_Get_Dist(void) {
    int dist_100;
    float cnt,distance;
    bool start = false;
    struct timeval start_time , end_time;
    gpio_write(TRIG,1);
    usleep(20);
    gpio_write(TRIG,0);
    int i = 0;

    while (i<33000) //33ms over time
    {
        if (!start)
        {
            if(gpio_read(ECHO)==1)
            {
                gettimeofday(&start_time,NULL);
                start = true;
            }
        }
        usleep(1);
        if (start)
        {
            if(gpio_read(ECHO)==0)
            {
                gettimeofday(&end_time,NULL);
                start = false;
                break;
            }
        }
        i++;
    }
    cnt = (end_time.tv_usec - start_time.tv_usec);
    cnt = cnt/1000;
    distance = 34 * cnt / 2;
    dist_100 = distance*100;

   if(dist_100>=0)
    {
        printf("Distance: %.2f cm\n",dist_100/100.0);
    }
    else
    {
        printf("距离测量超时\n");
    }

    return dist_100;
}